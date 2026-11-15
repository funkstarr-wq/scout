"""Tests for the owner's sign-in page, which guards the admin pages."""
import time

import pytest
from fastapi.testclient import TestClient

from scout import config, server
from scout.server import app

PASSWORD = "long-admin-password"


@pytest.fixture
def browser(monkeypatch):
    """A fresh browser with no cookies, on a site with an admin password."""
    monkeypatch.setattr(config, "ADMIN_PASSWORD", PASSWORD)
    return TestClient(app)


def sign_in(browser, password=PASSWORD, next_page="/admin/recordings", **headers):
    return browser.post("/admin/login", data={"password": password, "next": next_page},
                        headers=headers, follow_redirects=False)


def test_an_admin_page_sends_you_to_the_sign_in_page(browser):
    response = browser.get("/admin/recordings", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login?next=/admin/recordings"
    page = browser.get("/admin/recordings")  # a browser follows it
    assert 'type="password"' in page.text and 'name="next" value="/admin/recordings"' in page.text
    assert "WWW-Authenticate" not in response.headers  # no pop-up box


def test_there_is_no_sign_in_without_an_admin_password(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "")
    browser = TestClient(app)
    assert browser.get("/admin/login").status_code == 404
    assert browser.post("/admin/login", data={"password": ""}).status_code == 404


def test_the_right_password_signs_you_in_to_every_admin_page(browser):
    response = sign_in(browser)
    assert response.status_code == 303 and response.headers["location"] == "/admin/recordings"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Path=/admin" in cookie and "SameSite=lax" in cookie
    for page in ("/admin/recordings", "/admin/spend", "/admin/signups.csv", "/admin/login"):
        assert browser.get(page).status_code == 200
    assert browser.get("/admin/login", follow_redirects=False).headers["location"] == "/admin/recordings"


def test_the_cookie_is_https_only_on_the_live_site(browser):
    assert "Secure" in sign_in(browser, **{"X-Forwarded-Proto": "https"}).headers["set-cookie"]


def test_a_wrong_password_says_so_and_lets_nobody_in(browser):
    response = sign_in(browser, password="long-admin-passwore")
    assert response.status_code == 401
    assert "That password isn&#x27;t right" in response.text
    assert "set-cookie" not in response.headers
    assert browser.get("/admin/recordings", follow_redirects=False).status_code == 303


def test_the_page_after_signing_in_can_only_be_an_admin_page(browser):
    for sneaky in ("https://evil.example", "//evil.example", "/demo", "/admin/../demo"):
        assert sign_in(browser, next_page=sneaky).headers["location"] == "/admin/recordings"
    assert sign_in(browser, next_page="/admin/spend").headers["location"] == "/admin/spend"


def test_forged_or_expired_cookies_are_refused(browser):
    for ticket in ("1", "99999999999.abc", f"{int(time.time()) - 5}.x", server.admin_ticket(int(time.time()) - 5), "1" * 40 + ".x"):
        browser.cookies.set(server.ADMIN_COOKIE, ticket, path="/admin")
        assert browser.get("/admin/recordings", follow_redirects=False).status_code == 303
        browser.cookies.clear()


def test_changing_the_password_signs_everyone_out(browser, monkeypatch):
    sign_in(browser)
    assert browser.get("/admin/recordings").status_code == 200
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "a-brand-new-password")
    assert browser.get("/admin/recordings", follow_redirects=False).status_code == 303


def test_signing_out(browser):
    sign_in(browser)
    browser.get("/admin/logout")
    assert browser.get("/admin/recordings", follow_redirects=False).status_code == 303


def test_too_many_wrong_passwords_pause_signing_in(browser):
    for _ in range(server.WRONG_PASSWORD_LIMIT):
        assert sign_in(browser, password="guess").status_code == 401
    paused = sign_in(browser)  # even the right password, for now
    assert paused.status_code == 429 and "Too many wrong passwords" in paused.text
    assert browser.get("/admin/spend", auth=("admin", PASSWORD)).status_code == 401  # the old way too


def test_programs_can_still_send_the_password_with_each_request(browser):
    assert browser.get("/admin/spend", auth=("admin", PASSWORD)).status_code == 200
    assert browser.get("/admin/spend", auth=("someone", PASSWORD)).status_code == 401
