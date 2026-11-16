"""Tests for the owner's Readers page: everyone who asked for the free book."""
import csv
import io
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from scout import config, server, store
from scout.server import app

PASSWORD = "long-admin-password"


@pytest.fixture
def owner(monkeypatch):
    """A browser signed in as the site's owner."""
    monkeypatch.setattr(config, "ADMIN_PASSWORD", PASSWORD)
    browser = TestClient(app)
    browser.post("/admin/login", data={"password": PASSWORD, "next": "/admin/readers"}, follow_redirects=False)
    return browser


def reader(first="Ada", surname="Lovelace", email="ada@example.org", email_ok=True):
    return store.save_signup(first, surname, email, email_ok=email_ok)


def delete_form(check=None):
    return {"check": server.readers_check() if check is None else check, "reader": "ada@example.org"}


def test_the_readers_page_needs_signing_in(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", PASSWORD)
    response = TestClient(app).get("/admin/readers", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login?next=/admin/readers"


def test_admin_goes_to_the_readers_page(owner):
    assert owner.get("/admin", follow_redirects=False).headers["location"] == "/admin/readers"


def test_it_says_when_nobody_has_asked_yet(owner):
    page = owner.get("/admin/readers").text
    assert "Nobody has asked for the book yet" in page
    assert "<table hidden>" in page


def test_it_lists_every_reader_newest_first_with_totals(owner, monkeypatch):
    reader("Ada", "Lovelace", "ada@example.org", email_ok=True)
    later = store.utcnow() + timedelta(minutes=5)
    monkeypatch.setattr(store, "utcnow", lambda: later)
    reader("Grace", "Hopper", "grace@example.org", email_ok=False)
    page = owner.get("/admin/readers").text
    assert page.index("Grace Hopper") < page.index("Ada Lovelace")
    assert '<b>2</b><span>readers</span>' in page
    assert '<b>1</b><span>happy to get emails</span>' in page
    assert '<b>2</b><span>new in the last 7 days</span>' in page
    assert 'href="mailto:ada@example.org"' in page


def test_search_finds_readers_by_name_or_email(owner):
    reader("Ada", "Lovelace", "ada@example.org")
    reader("Grace", "Hopper", "grace@navy.example")
    page = owner.get("/admin/readers", params={"q": "  NAVY  "}).text
    assert "Grace Hopper" in page and "Ada Lovelace" not in page
    assert 'value="NAVY"' in page
    page = owner.get("/admin/readers", params={"q": "ada love"}).text
    assert "Ada Lovelace" in page and "Grace Hopper" not in page
    assert "Nobody matches that search" in owner.get("/admin/readers", params={"q": "nobody"}).text


def test_names_readers_typed_can_never_run_as_code(owner):
    reader("<script>alert(1)</script>", "');alert(2);('", "sneaky@example.org")
    page = owner.get("/admin/readers").text
    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &#x27;);alert(2);(&#x27;" in page
    assert "onsubmit" not in page  # the delete question reads the name as text, from data-name


def test_a_long_list_shows_the_newest_and_says_how_to_find_the_rest(owner, monkeypatch):
    monkeypatch.setattr(server, "READERS_SHOWN", 2)
    for n in range(3):
        reader("Reader", str(n), f"r{n}@example.org")
    page = owner.get("/admin/readers").text
    assert "Showing the newest 2. Search to find the other 1" in page


def test_deleting_a_reader_removes_them_and_their_download_links(owner):
    token = reader()
    response = owner.post("/admin/readers/delete", data=delete_form(), follow_redirects=False)
    assert response.headers["location"] == "/admin/readers?done=deleted"
    assert store.list_signups() == []
    assert "Deleted. That reader" in owner.get(response.headers["location"]).text
    assert owner.get(f"/book/{token}/pdf").status_code == 404
    again = owner.post("/admin/readers/delete", data=delete_form(), follow_redirects=False)
    assert again.headers["location"] == "/admin/readers?done=missing"


def test_deleting_needs_the_pages_own_check_code(owner):
    reader()
    assert owner.post("/admin/readers/delete", data=delete_form(check="guess")).status_code == 403
    assert len(store.list_signups()) == 1


def test_deleting_needs_signing_in(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", PASSWORD)
    reader()
    response = TestClient(app).post("/admin/readers/delete", data=delete_form(), follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].startswith("/admin/login")
    assert len(store.list_signups()) == 1


def test_a_spreadsheet_of_only_the_people_happy_to_get_emails(owner):
    reader("Ada", "Lovelace", "ada@example.org", email_ok=True)
    reader("Grace", "Hopper", "grace@example.org", email_ok=False)
    sheet = owner.get("/admin/signups.csv", params={"only": "email_ok"})
    assert "happy-to-get-emails" in sheet.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(sheet.text)))
    assert [r[2] for r in rows[1:]] == ["ada@example.org"]
    everyone = list(csv.reader(io.StringIO(owner.get("/admin/signups.csv").text)))
    assert len(everyone) == 3
