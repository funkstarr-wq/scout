"""Tests for the free book: the form, the download links, the readers' list and the fonts."""
import csv
import html
import io
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from scout import config, store
from scout.server import app

client = TestClient(app)
LINKEDIN = "https://www.linkedin.com/in/chris-haworth-98605b27/"


def ask_for_book(**fields):
    form = {"first_name": "Ada", "surname": "Lovelace", "email": "ada@example.org", **fields}
    return client.post("/book", data=form)


def download_links(page):
    return re.findall(r'href="(/book/[^"]+/(?:pdf|epub))"', page.text)


def signups():
    return store.list_signups()


# --------------------------------------------------------------------- the page
def test_website_offers_the_free_book_and_links_to_linkedin():
    page = client.get("/").text
    assert 'action="/book"' in page and 'id="free"' in page
    for field in ('name="first_name"', 'name="surname"', 'name="email"', 'name="email_ok"'):
        assert field in page
    assert page.count(LINKEDIN) == 2  # about the author, and the footer
    assert "Charis SIL" in page


def test_book_files_are_in_the_project():
    assert (config.BOOK_DIR / "Building-Scout.pdf").read_bytes()[:4] == b"%PDF"
    assert (config.BOOK_DIR / "Building-Scout.epub").read_bytes()[:2] == b"PK"


# --------------------------------------------------------------------- the form
def test_filling_in_the_form_gives_download_links():
    page = ask_for_book(email_ok="yes")
    assert page.status_code == 200
    assert "Thanks, Ada" in page.text
    links = download_links(page)
    assert [link.rsplit("/", 1)[1] for link in links] == ["pdf", "epub"]
    [reader] = signups()
    assert (reader["first_name"], reader["surname"], reader["email"], reader["email_ok"]) == \
        ("Ada", "Lovelace", "ada@example.org", 1)


def test_emails_are_only_ok_if_the_box_is_ticked():
    ask_for_book()
    assert signups()[0]["email_ok"] == 0


@pytest.mark.parametrize("fields, message", [
    ({"first_name": ""}, "Please add your name"),
    ({"surname": "   "}, "Please add your name"),
    ({"first_name": "x" * 61}, "Please add your name"),
    ({"email": "not-an-email"}, "Please check your email address"),
    ({"email": "ada@example"}, "Please check your email address"),
    ({"website": "http://spam.example"}, "Something went wrong"),  # the hidden box only robots fill in
])
def test_incomplete_forms_are_refused_and_nothing_is_saved(fields, message):
    page = ask_for_book(**fields)
    assert page.status_code == 400
    assert message in page.text
    assert download_links(page) == []
    assert signups() == []


def test_typed_names_cannot_add_html_to_the_page():
    page = ask_for_book(first_name="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in page.text
    assert "&lt;script&gt;" in page.text


def test_an_oversized_form_is_refused():
    page = client.post("/book", content=b"first_name=" + b"x" * 20_000,
                       headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert page.status_code == 413
    assert signups() == []


def test_asking_again_updates_the_reader_instead_of_adding_a_second_one():
    first = download_links(ask_for_book(email_ok="yes"))[0]
    second = download_links(ask_for_book(first_name="Augusta", email="ADA@example.org"))[0]
    [reader] = signups()
    assert reader["first_name"] == "Augusta" and reader["email_ok"] == 0
    assert client.get(first).status_code == 404     # the old link was replaced
    assert client.get(second).status_code == 200


def test_get_on_the_form_address_goes_back_to_the_form():
    response = client.get("/book", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/#free"


# ------------------------------------------------------------------ downloading
def test_download_links_give_the_pdf_and_the_epub():
    pdf_link, epub_link = download_links(ask_for_book())
    pdf = client.get(pdf_link)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert 'filename="Building-Scout.pdf"' in pdf.headers["content-disposition"]
    assert pdf.content[:4] == b"%PDF"
    epub = client.get(epub_link)
    assert epub.headers["content-type"] == "application/epub+zip"
    assert epub.content[:2] == b"PK"
    assert signups()[0]["downloads"] == 2


@pytest.mark.parametrize("path", ["/book/made-up-token-1234567890/pdf", "/book/x/epub"])
def test_made_up_links_do_not_download(path):
    page = client.get(path)
    assert page.status_code == 404
    assert "doesn't work" in html.unescape(page.text)


def test_only_pdf_and_epub_can_be_downloaded():
    token = download_links(ask_for_book())[0].split("/")[2]
    assert client.get(f"/book/{token}/docx").status_code == 404
    assert client.get(f"/book/{token}/..%2F..%2FBuilding-Scout.docx").status_code == 404


def test_links_expire_after_a_week(monkeypatch):
    link = download_links(ask_for_book())[0]
    later = datetime.now(timezone.utc) + timedelta(days=config.BOOK_LINK_DAYS, hours=1)
    monkeypatch.setattr(store, "utcnow", lambda: later)
    page = client.get(link)
    assert page.status_code == 410
    assert "expired" in page.text


def test_book_works_in_the_live_demo_too(demo):
    links = download_links(TestClient(app).post("/book", data={"first_name": "Grace", "surname": "Hopper",
                                                                "email": "grace@example.org"}))
    assert TestClient(app).get(links[1]).status_code == 200


# ---------------------------------------------------------------- readers' list
def test_readers_list_does_not_exist_without_an_admin_password(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "")
    assert client.get("/admin/signups.csv", auth=("admin", "")).status_code == 404


def test_readers_list_needs_the_admin_password(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "long-admin-password")
    ask_for_book(email_ok="yes")
    assert client.get("/admin/signups.csv").status_code == 401
    assert client.get("/admin/signups.csv", auth=("admin", "wrong")).status_code == 401
    assert client.get("/admin/signups.csv", auth=("scout", "long-admin-password")).status_code == 401
    sheet = client.get("/admin/signups.csv", auth=("admin", "long-admin-password"))
    assert sheet.status_code == 200
    rows = list(csv.reader(io.StringIO(sheet.text)))
    assert rows[0][:4] == ["First name", "Surname", "Email", "Happy to get emails"]
    assert rows[1][:4] == ["Ada", "Lovelace", "ada@example.org", "yes"]


def test_readers_list_is_safe_to_open_in_a_spreadsheet(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "long-admin-password")
    ask_for_book(first_name="=HYPERLINK(\"http://evil.example\")")
    rows = list(csv.reader(io.StringIO(client.get("/admin/signups.csv", auth=("admin", "long-admin-password")).text)))
    assert rows[1][0].startswith("'=")


def test_privacy_note_explains_the_book_form():
    page = client.get("/privacy").text
    assert "If you ask for the free book" in page
    assert "never shared or sold" in page


# ------------------------------------------------------------------------ fonts
def test_the_cover_font_is_served():
    font = client.get("/fonts/charis-sil-latin-400-normal.woff2")
    assert font.status_code == 200
    assert font.headers["content-type"] == "font/woff2"


@pytest.mark.parametrize("name", ["OFL.txt", "..%2F..%2Fconfig.py", "charis-sil-latin-900-normal.woff2"])
def test_only_the_font_files_are_served(name):
    assert client.get(f"/fonts/{name}").status_code == 404
