"""Tests for the live demo's limits. Everything uses the pretend Claude: no real API calls."""
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from scout import config, llm, store
from scout.agents import research_subtask
from scout.graph import run_research
from scout.server import app, slots, visitor_ip
from tests.fake_llm import FakeClient

ROOT = Path(__file__).resolve().parent.parent
QUESTION = "What are facts A and B?"


def visitor(ip="203.0.113.10"):
    """A browser of its own (with its own cookie), coming from one internet address."""
    return TestClient(app, headers={"X-Real-IP": ip})


def ask(client, question=QUESTION):
    return client.post("/api/research", json={"question": question})


def jobs_in_database():
    with store._connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


def pretend_it_is(monkeypatch, when):
    monkeypatch.setattr(store, "utcnow", lambda: when)


# ------------------------------------------------------------------ per visitor
def test_third_question_from_a_visitor_is_refused(demo):
    browser = visitor()
    assert ask(browser).status_code == 200
    assert ask(browser).status_code == 200
    third = ask(browser)
    assert third.status_code == 429
    assert "You've used your 2 questions for today" in third.json()["detail"]


def test_x_real_ip_tells_visitors_apart_in_the_demo(demo):
    # The same browser from two addresses counts as two visitors, because Railway's
    # X-Real-IP header is what identifies a visitor in the demo.
    browser = TestClient(app)
    for _ in range(2):
        assert browser.post("/api/research", json={"question": QUESTION}, headers={"X-Real-IP": "198.51.100.1"}).status_code == 200
    assert browser.post("/api/research", json={"question": QUESTION}, headers={"X-Real-IP": "198.51.100.1"}).status_code == 429
    assert browser.post("/api/research", json={"question": QUESTION}, headers={"X-Real-IP": "198.51.100.2"}).status_code == 200


def test_x_real_ip_is_only_trusted_in_the_demo(monkeypatch):
    scope = {"type": "http", "headers": [(b"x-real-ip", b"198.51.100.7")], "client": ("10.0.0.1", 5000)}
    monkeypatch.setattr(config, "DEMO_MODE", False)
    assert visitor_ip(Request(scope)) == "10.0.0.1"
    monkeypatch.setattr(config, "DEMO_MODE", True)
    assert visitor_ip(Request(scope)) == "198.51.100.7"


# ---------------------------------------------------------------- everyone's cap
def test_daily_cap_stops_even_a_new_visitor(demo, monkeypatch):
    monkeypatch.setattr(config, "DAILY_LIMIT", 2)
    assert ask(visitor("192.0.2.1")).status_code == 200
    assert ask(visitor("192.0.2.2")).status_code == 200
    refused = ask(visitor("192.0.2.3"))
    assert refused.status_code == 429
    assert "all the questions it can afford today" in refused.json()["detail"]


def test_questions_at_the_same_moment_cannot_exceed_the_daily_cap():
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: store.try_create_job(QUESTION, daily_limit=3), range(12)))
    assert sum(job_id is not None for job_id, _ in results) == 3
    assert jobs_in_database() == 3


def test_questions_at_the_same_moment_cannot_exceed_the_visitor_limit():
    def one(_):
        return store.try_create_job(QUESTION, daily_limit=100, ip_hash="same-visitor", per_visitor_limit=2)

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(one, range(12)))
    assert sum(job_id is not None for job_id, _ in results) == 2


# ------------------------------------------------------------------ question size
@pytest.mark.parametrize("length, allowed", [(9, False), (10, True), (300, True), (301, False)])
def test_question_length_in_the_demo(demo, length, allowed):
    question = "  " + "x" * length + "  "  # spaces at either end don't count
    response = ask(visitor(f"192.0.2.{length % 250}"), question)
    assert response.status_code == (200 if allowed else 400)


# ------------------------------------------------------------------- a new day
def test_limits_reset_the_next_utc_day(demo, monkeypatch):
    pretend_it_is(monkeypatch, datetime(2026, 11, 11, 23, 30, tzinfo=timezone.utc))
    browser = visitor()
    assert ask(browser).status_code == 200
    assert ask(browser).status_code == 200
    assert ask(browser).status_code == 429
    pretend_it_is(monkeypatch, datetime(2026, 11, 12, 0, 5, tzinfo=timezone.utc))
    assert ask(browser).status_code == 200


# ------------------------------------------------------------------ one at a time
def test_busy_refusal_does_not_use_up_a_question(demo, monkeypatch):
    monkeypatch.setattr(slots, "running", config.MAX_CONCURRENT)  # someone else's question is running
    browser = visitor()
    busy = ask(browser)
    assert busy.status_code == 503
    assert "busy" in busy.json()["detail"]
    assert jobs_in_database() == 0

    monkeypatch.setattr(slots, "running", 0)  # that question finished
    assert ask(browser).status_code == 200
    assert ask(browser).status_code == 200  # still two questions available


def test_a_finished_question_frees_its_slot(demo):
    assert ask(visitor()).status_code == 200
    assert slots.running == 0


# ----------------------------------------------------------------------- privacy
def test_no_raw_ip_in_the_database_or_logs(demo, caplog):
    secret_ip = "203.0.113.77"
    with caplog.at_level("DEBUG"):
        assert ask(visitor(secret_ip)).status_code == 200
    assert secret_ip.encode() not in Path(config.DB_PATH).read_bytes()
    assert secret_ip not in caplog.text


def test_each_visitor_sees_only_their_own_questions(demo):
    alice, bob = visitor("192.0.2.10"), visitor("192.0.2.20")
    alice_job = ask(alice, "What is Alice's question about facts?").json()["id"]
    bob_job = ask(bob, "What is Bob's question about facts?").json()["id"]

    assert [j["id"] for j in alice.get("/api/history").json()] == [alice_job]
    assert [j["id"] for j in bob.get("/api/history").json()] == [bob_job]
    assert alice.get(f"/api/research/{alice_job}").status_code == 200
    assert alice.get(f"/api/research/{bob_job}").status_code == 404
    assert "visitor_id" not in alice.get(f"/api/research/{alice_job}").json()
    assert visitor("192.0.2.30").get("/api/history").json() == []


def test_demo_page_gives_the_visitor_a_cookie(demo):
    browser = TestClient(app)
    browser.get("/demo")
    assert browser.cookies.get("scout_visitor")


def test_old_demo_questions_are_deleted_after_30_days(demo, monkeypatch):
    now = datetime.now(timezone.utc)
    pretend_it_is(monkeypatch, now - timedelta(days=31))
    store.try_create_job("An old question from last month", daily_limit=10)
    pretend_it_is(monkeypatch, now - timedelta(days=29))
    store.try_create_job("A question from four weeks ago", daily_limit=10)
    pretend_it_is(monkeypatch, now)

    with TestClient(app):  # starting the app runs the clean-up
        pass
    assert [j["question"] for j in store.list_jobs()] == ["A question from four weeks ago"]


# ---------------------------------------------------------------- cheaper effort
def test_time_limit_stops_a_slow_run():
    with pytest.raises(TimeoutError):
        run_research(QUESTION, time_limit=0)


def test_researcher_past_its_deadline_spends_nothing(fake_claude):
    findings = research_subtask(QUESTION, {"title": "Part A", "objective": "Find A.", "search_hints": []},
                                deadline=time.monotonic() - 1)
    assert findings == []
    assert fake_claude.messages.calls == []


def test_demo_skips_the_rewrite(monkeypatch):
    monkeypatch.setattr(config, "MAX_REVISIONS", 0)
    client = FakeClient(approve=False)
    llm.set_client(client)
    progress = []
    run_research(QUESTION, on_progress=progress.append)
    writer_calls = [c for c in client.messages.calls if not c.get("tools")]
    assert len(writer_calls) == 1
    assert "skips rewrites" in progress[-1]


def run_python(code, **env):
    """Start a fresh Python, as Railway would, with these settings."""
    settings = {**os.environ, "PYTHONPATH": str(ROOT), **env}
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=settings, capture_output=True, text=True)


def test_demo_mode_uses_the_cheaper_effort_settings():
    code = ("from scout import config, tools; "
            "print(config.MAX_SUBTASKS, config.MAX_SEARCHES_PER_RESEARCHER, config.MAX_REVISIONS, "
            "tools.WEB_SEARCH_TOOL['max_uses'])")
    assert run_python(code, DEMO_MODE="1").stdout.split() == ["3", "3", "0", "3"]
    assert run_python(code, DEMO_MODE="0").stdout.split() == ["5", "5", "1", "5"]


# ---------------------------------------------------------- refusing to start
def test_demo_refuses_to_start_without_a_salt():
    result = run_python("import scout.server", DEMO_MODE="1", SCOUT_IP_SALT="")
    assert result.returncode != 0
    assert "SCOUT_IP_SALT" in result.stderr


def test_demo_starts_with_a_salt():
    result = run_python("import scout.server", DEMO_MODE="1", SCOUT_IP_SALT="a-long-random-test-salt")
    assert result.returncode == 0, result.stderr


def test_a_mistyped_daily_limit_refuses_to_start():
    result = run_python("import scout.config", SCOUT_DAILY_LIMIT="twenty")
    assert result.returncode != 0
    assert "SCOUT_DAILY_LIMIT must be a whole number" in result.stderr


# ----------------------------------------------------------------- fake mode
def test_fake_mode_uses_the_pretend_claude(monkeypatch):
    monkeypatch.setattr(config, "FAKE_MODE", True)
    llm.set_client(None)
    assert isinstance(llm.client(), FakeClient)
    assert TestClient(app).get("/api/settings").json()["fake"] is True
