"""Tests for what search engines and AI assistants see: robots.txt, the site map, llms.txt,
the structured data on the home page and the server-written example reports."""
import html
import json
import re
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from scout import config, examples, seo, store
from scout.server import app

client = TestClient(app)
SITE = "https://buildingscout.info"


@pytest.fixture
def no_files(tmp_path, monkeypatch):
    """No saved example files, so only runs saved in the test database count."""
    monkeypatch.setattr(examples, "EXAMPLES_DIR", tmp_path)


def json_ld(page_text):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page_text, re.S)
    assert len(blocks) == 1
    return json.loads(blocks[0])


# ------------------------------------------------------------------ robots.txt
def test_robots_txt_welcomes_everyone_but_keeps_private_pages_out():
    response = client.get("/robots.txt")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/plain")
    robots = RobotFileParser()
    robots.parse(response.text.splitlines())
    for bot in ("*", "Googlebot", "GPTBot", "ClaudeBot", "PerplexityBot"):
        for page in ("/", "/demo", "/privacy", "/examples/coffee-and-sleep", "/llms.txt"):
            assert robots.can_fetch(bot, SITE + page), (bot, page)
        for page in ("/admin/readers", "/admin/login", "/api/settings", "/book/some-token/pdf"):
            assert not robots.can_fetch(bot, SITE + page), (bot, page)
    assert f"Sitemap: {SITE}/sitemap.xml" in response.text


# ----------------------------------------------------------------- sitemap.xml
def test_the_site_map_lists_the_public_pages(no_files):
    response = client.get("/sitemap.xml")
    assert response.headers["content-type"].startswith("application/xml")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in ElementTree.fromstring(response.text).findall("s:url/s:loc", ns)]
    assert locs == [f"{SITE}/", f"{SITE}/demo", f"{SITE}/privacy"]


def test_the_site_map_adds_example_reports_once_they_are_recorded(no_files):
    store.save_recording("coffee-and-sleep", {"report": "Coffee can delay sleep [1].", "made_at": "2026-11-16T09:00:00+00:00"})
    text = client.get("/sitemap.xml").text
    assert f"<loc>{SITE}/examples/coffee-and-sleep</loc><lastmod>2026-11-16</lastmod>" in text
    assert "heat-pumps" not in text  # not recorded yet, so it's only a "coming soon" page


# -------------------------------------------------------------------- llms.txt
def test_llms_txt_summarises_the_site_for_ai_assistants(no_files):
    text = client.get("/llms.txt").text
    assert text.startswith("# Building Scout\n\n> Building Scout is a free book by Christopher Haworth")
    assert "{{" not in text
    assert f"[Get the book free]({SITE}/#free)" in text and f"[Demo]({SITE}/demo)" in text
    assert "15. Shipping Scout" in text
    for question, answer in seo.faq():
        assert f"### {question}\n{answer}" in text
    assert "Example report" not in text  # nothing recorded yet


def test_llms_txt_links_recorded_example_reports(no_files):
    store.save_recording("coffee-and-sleep", {"report": "Coffee can delay sleep by about [an hour](https://x.example) [1].\n\n## Sources"})
    text = client.get("/llms.txt").text
    assert (f"- [Example report: Does drinking coffee affect how well you sleep?]({SITE}/examples/coffee-and-sleep): "
            "Coffee can delay sleep by about an hour.") in text


# -------------------------------------------------------------- the home page
def test_the_faq_file_has_the_questions_and_skips_its_notes():
    pairs = seo.faq()
    assert len(pairs) >= 6
    assert pairs[0][0] == "What is Building Scout?"
    assert all(q.endswith("?") and a for q, a in pairs)
    assert not any("plain sentences" in a for _, a in pairs)  # the note at the top isn't a question


def test_the_home_page_shows_the_faq_and_says_the_same_in_its_structured_data():
    page = client.get("/").text
    data = json_ld(page)
    kinds = {item["@type"]: item for item in data["@graph"]}
    assert set(kinds) == {"WebSite", "Book", "Person", "FAQPage"}
    book, person = kinds["Book"], kinds["Person"]
    assert book["isAccessibleForFree"] is True and book["offers"]["price"] == "0"
    assert book["author"] == {"@id": f"{SITE}/#author"} == {"@id": person["@id"]}
    assert person["name"] == "Christopher Haworth"
    assert "https://www.linkedin.com/in/chris-haworth-98605b27/" in person["sameAs"]
    questions = kinds["FAQPage"]["mainEntity"]
    assert [(q["name"], q["acceptedAnswer"]["text"]) for q in questions] == seo.faq()
    for question, answer in seo.faq():  # search engines want the answers visible on the page too
        assert f"<h3>{html.escape(question)}</h3><p>{html.escape(answer)}</p>" in page
    assert "{{" not in page


def test_the_site_address_is_the_same_everywhere():
    assert config.SITE_URL == SITE
    page = client.get("/").text
    assert f'<link rel="canonical" href="{SITE}/">' in page
    assert f'<link rel="canonical" href="{SITE}/demo">' in client.get("/demo").text
    assert f'<link rel="canonical" href="{SITE}/privacy">' in client.get("/privacy").text


@pytest.mark.parametrize("path", ["/", "/demo", "/privacy"])
def test_public_pages_have_a_description(path):
    assert re.search(r'<meta name="description" content="[^"]{50,}">', client.get(path).text)


# ------------------------------------------------------------ private pages
@pytest.mark.parametrize("path", ["/admin/login", "/api/settings", "/book/made-up-token/pdf"])
def test_private_pages_ask_not_to_be_indexed(path, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "long-admin-password")
    assert client.get(path, follow_redirects=False).headers.get("x-robots-tag") == "noindex, nofollow"


def test_public_pages_can_be_indexed():
    assert "x-robots-tag" not in client.get("/").headers
    assert '<meta name="robots" content="noindex">' in client.get("/examples/heat-pumps-vs-gas-boilers").text  # coming soon


# ------------------------------------------------------- example report pages
REPORT = """# Coffee and sleep

Coffee can delay sleep by about **an hour** [1]. See [the study](https://example.org/study?a=1&b=2) [2].

- Caffeine lasts hours [1]
- <script>alert(1)</script> is just text
- [a trick](javascript:alert(2))

## Sources

1. [A study](https://example.org/one)
2. [Another](https://example.org/two)
"""


def test_example_reports_are_written_into_the_page_for_tools_that_skip_javascript(no_files):
    store.save_recording("coffee-and-sleep", {
        "question": examples.EXAMPLES["coffee-and-sleep"], "report": REPORT, "made_at": "2026-11-16T09:00:00+00:00",
        "sources": [{"n": 1, "url": "https://example.org/one", "title": "A study"},
                    {"n": 2, "url": "javascript:alert(3)", "title": "Not a web page"}]})
    page = client.get("/examples/coffee-and-sleep").text
    assert "<title>Does drinking coffee affect how well you sleep? · Example report by Scout</title>" in page
    assert '<meta name="description" content="Coffee can delay sleep by about an hour. See the study.">' in page
    assert f'<link rel="canonical" href="{SITE}/examples/coffee-and-sleep">' in page
    assert '<h1 id="question">Does drinking coffee affect how well you sleep?</h1>' in page
    assert "<p>Coffee can delay sleep by about <strong>an hour</strong> [1]." in page
    assert '<a href="https://example.org/study?a=1&amp;b=2" rel="nofollow noopener">the study</a>' in page
    assert "<h2>Sources</h2>" in page and "<ol><li><a href=\"https://example.org/one\"" in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; is just text" in page
    assert "<script>alert(1)" not in page and 'href="javascript' not in page
    data = json_ld(page)
    assert data["@type"] == "Report" and data["datePublished"] == "2026-11-16T09:00:00+00:00"
    assert data["citation"] == ["https://example.org/one"]
    assert "{{" not in page


# ----------------------------------------------------- proving who owns the site
def test_google_search_console_can_find_its_verification_file():
    response = client.get("/google0bea272a8c90e707.html")
    assert response.status_code == 200
    assert response.text == "google-site-verification: google0bea272a8c90e707.html"


@pytest.mark.parametrize("path", ["/google0000000000000000.html", "/index.html", "/googlexyz.html", "/faq.html"])
def test_only_real_verification_files_are_served(path):
    assert client.get(path).status_code == 404


# ------------------------------------------------------------- HEAD requests
@pytest.mark.parametrize("path, kind", [("/", "text/html"), ("/sitemap.xml", "application/xml"),
                                        ("/robots.txt", "text/plain"), ("/llms.txt", "text/plain"),
                                        ("/google0bea272a8c90e707.html", "text/html"), ("/demo", "text/html")])
def test_head_requests_are_answered_like_get_without_the_page(path, kind):
    response = client.head(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(kind)
    assert response.content == b""
    assert int(response.headers["content-length"]) == len(client.get(path).content)


def test_head_still_redirects_www_and_finds_missing_pages():
    assert client.head("/sitemap.xml", headers={"host": "www.buildingscout.info"}, follow_redirects=False).status_code == 301
    assert client.head("/no-such-page.html").status_code == 404


def test_checking_a_download_link_does_not_count_as_a_download():
    token = store.save_signup("Ada", "Lovelace", "ada@example.org", email_ok=False)
    assert client.head(f"/book/{token}/pdf").status_code != 200
    assert store.find_signup(token)["downloads"] == 0
