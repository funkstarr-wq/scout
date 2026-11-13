"""Tests for the website, the demo page, the example reports and who needs a password."""
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scout import config, examples, llm
from scout.server import app

ROOT = Path(__file__).resolve().parent.parent
client = TestClient(app)


class NoClaudeAllowed:
    """Fails the test if anything tries to call Claude."""

    class messages:
        @staticmethod
        def create(**kwargs):
            raise AssertionError("This page must never call the Claude API")


@pytest.fixture
def saved_example(tmp_path, monkeypatch):
    monkeypatch.setattr(examples, "EXAMPLES_DIR", tmp_path)
    data = {"name": "coffee-and-sleep", "question": examples.EXAMPLES["coffee-and-sleep"],
            "report": "Coffee can delay sleep [1].\n\n## Sources\n\n1. [A study](https://example.org)\n",
            "progress": ["Planned 3 research task(s)", "Wrote a draft report"]}
    (tmp_path / "coffee-and-sleep.json").write_text(json.dumps(data))
    return data


# ------------------------------------------------------------------ the website
def test_website_is_at_the_front_door():
    page = client.get("/")
    assert page.status_code == 200
    assert "Building Scout" in page.text
    assert client.get("/cover.jpg").headers["content-type"] == "image/jpeg"
    assert client.get("/og-image.jpg").status_code == 200


def test_scout_page_has_moved_to_demo_and_carries_the_banner():
    page = client.get("/demo")
    assert page.status_code == 200
    assert "Research it" in page.text
    # The banner is part of the page; the page shows it when /api/settings says the demo is on.
    assert "Live demo. Limited questions per day. Questions are stored." in page.text
    assert client.get("/api/settings").json()["demo"] is False


def test_privacy_note():
    assert "deleted automatically after 30 days" in client.get("/privacy").text


# ---------------------------------------------------------------- the password
def test_website_and_examples_are_public_but_scout_needs_the_password(monkeypatch):
    monkeypatch.setattr(config, "PASSWORD", "s3cret")
    assert client.get("/").status_code == 200
    assert client.get("/examples/coffee-and-sleep").status_code == 200
    assert client.get("/privacy").status_code == 200
    assert client.get("/demo").status_code == 401
    assert client.get("/demo", auth=("scout", "s3cret")).status_code == 200


def test_demo_needs_no_password(demo, monkeypatch):
    monkeypatch.setattr(config, "PASSWORD", "s3cret")
    browser = TestClient(app, headers={"X-Real-IP": "192.0.2.50"})
    for path in ("/", "/demo", "/examples/coffee-and-sleep", "/api/history"):
        assert browser.get(path).status_code == 200, path
    assert browser.post("/api/research", json={"question": "What are facts A and B?"}).status_code == 200


def test_settings_tell_the_page_about_the_demo(demo):
    settings = client.get("/api/settings").json()
    assert settings["demo"] is True and settings["max_chars"] == 300
    assert [e["name"] for e in settings["examples"]] == list(examples.EXAMPLES)


# ------------------------------------------------------------ example reports
def test_example_report_never_calls_claude(saved_example):
    llm.set_client(NoClaudeAllowed())
    page = client.get("/examples/coffee-and-sleep")
    assert page.status_code == 200
    assert "Example report" in page.text
    assert client.get("/api/examples/coffee-and-sleep").json() == saved_example


def test_example_not_made_yet_says_coming_soon(tmp_path, monkeypatch):
    monkeypatch.setattr(examples, "EXAMPLES_DIR", tmp_path)  # an empty folder
    page = client.get("/examples/heat-pumps-vs-gas-boilers")
    assert page.status_code == 200
    assert "coming soon" in page.text
    assert client.get("/api/examples/heat-pumps-vs-gas-boilers").status_code == 404


@pytest.mark.parametrize("path", ["/examples/no-such-report", "/examples/..%2F..%2Fconfig",
                                  "/examples/../../scout/config.py", "/api/examples/..%2Fsite"])
def test_unknown_or_sneaky_example_names_get_a_404(saved_example, path):
    assert client.get(path).status_code == 404


def test_only_listed_names_are_loaded(saved_example):
    assert examples.load("../coffee-and-sleep") is None
    assert examples.load("coffee-and-sleep") == saved_example


def test_make_examples_saves_a_report_with_its_progress_log(tmp_path):
    spec = importlib.util.spec_from_file_location("make_examples", ROOT / "scripts" / "make_examples.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    path = script.make_one("coffee-and-sleep", tmp_path)
    saved = json.loads(path.read_text())
    assert saved["question"] == examples.EXAMPLES["coffee-and-sleep"]
    assert "## Sources" in saved["report"]
    assert saved["progress"][0].startswith("Planned")
    assert set(saved["settings"]) >= {"lead_model", "worker_model", "max_subtasks", "max_revisions"}


def test_make_examples_uses_the_demo_settings_and_asks_before_spending():
    import os
    import subprocess
    import sys

    env = {**os.environ, "DEMO_MODE": "0", "SCOUT_FAKE": "0"}  # the script must switch the demo on itself
    result = subprocess.run([sys.executable, "scripts/make_examples.py"], cwd=ROOT, env=env,
                            input="no\n", capture_output=True, text=True)
    assert "up to 3 researchers, 3 searches each, no rewrite" in result.stdout
    assert "Nothing was spent" in result.stdout
