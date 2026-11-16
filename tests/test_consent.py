"""Tests for Google Tag Manager and the cookie banner: nothing from Google without the visitor's OK."""
import re

import pytest
from fastapi.testclient import TestClient

from scout import config
from scout.server import app

client = TestClient(app)
TAG = '<script src="/site-consent.js" defer></script>'


def test_the_banner_script_carries_the_container_id_and_starts_with_everything_denied():
    response = client.get("/site-consent.js")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/javascript")
    script = response.text
    assert 'const GTM_ID = "GTM-PNRC4M8Q";' in script
    denied = script.index('gtag("consent", "default"')
    loader = script.index("googletagmanager.com/gtm.js")
    assert denied < loader  # consent is set to "denied" before anything could load
    assert re.search(r'ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied", '
                     r'analytics_storage: "denied"', script)
    assert '{ analytics_storage: "granted" }' in script and 'ad_storage: "granted"' not in script  # never advertising
    # Google's script is only ever added inside loadTagManager(), which runs after "Accept" (or a remembered yes).
    body = script[script.index("function loadTagManager"):]
    assert body.index("googletagmanager.com/gtm.js") < body.index("function forgetAnalyticsCookies")


@pytest.mark.parametrize("value", ["", "not-an-id", 'GTM-ABC"; alert(1); "'])
def test_a_missing_or_odd_container_id_switches_it_off(monkeypatch, value):
    monkeypatch.setattr(config, "GTM_ID", value)
    script = client.get("/site-consent.js").text
    assert 'const GTM_ID = "";' in script and "alert(1)" not in script


def test_rejecting_is_as_easy_as_accepting():
    script = client.get("/site-consent.js").text
    assert '<button type="button" data-choice="yes">Accept</button>' in script
    assert '<button type="button" data-choice="no">No thanks</button>' in script


@pytest.mark.parametrize("path", ["/", "/demo", "/privacy", "/examples/heat-pumps-vs-gas-boilers", "/examples/no-such-report"])
def test_public_pages_load_the_banner(path):
    assert TAG in client.get(path).text


def test_the_book_and_owner_pages_never_load_it(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "long-admin-password")
    ready = client.post("/book", data={"first_name": "Ada", "surname": "Lovelace", "email": "ada@example.org"})
    problem = client.post("/book", data={"first_name": "", "surname": "", "email": ""})
    owner = TestClient(app)
    owner.post("/admin/login", data={"password": "long-admin-password", "next": "/admin/readers"})
    pages = [ready.text, problem.text, owner.get("/admin/login").text, owner.get("/admin/readers").text,
             owner.get("/admin/recordings").text]
    for page in pages:
        assert "site-consent.js" not in page and "googletagmanager" not in page


def test_the_privacy_note_explains_the_cookies_and_lets_you_change_your_mind():
    page = client.get("/privacy").text
    assert 'id="cookies"' in page and "Google Analytics" in page
    assert "Nothing from Google loads\n  unless you press Accept." in page
    assert "<button type=\"button\" data-cookie-choice>Change your cookie choice</button>" in page
    assert "no analytics" not in page.lower()
