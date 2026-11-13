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
from scout.server import app, slots, visitor_ip, visitor_network
from tests.fake_llm import FakeClient

ROOT = Path(__file__).resolve().parent.parent
QUESTION = "What are facts A and B?"


def visitor(ip="203.0.113.10"):
    """A browser of its own, coming from one internet address, that has opened the demo page (so it has its cookie)."""
    browser = TestClient(app, headers={"X-Real-IP": ip})
    browser.get("/demo")
    return browser


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
    browser.get("/demo")
    for _ in range(2):
        assert browser.post("/api/research", json={"question": QUESTION}, headers={"X-Real-IP": "198.51.100.1"}).status_code == 200
    assert browser.post("/api/research", json={"question": QUESTION}, headers={"X-Real-IP": "198.51.100.1"}).status_code == 429
    assert browser.post("/api/research", json={"question": QUESTION}, headers={"X-Real-IP": "198.51.100.2"}).status_code == 200


def test_a_homes_whole_ipv6_block_counts_as_one_visitor(demo):
    assert visitor_network("2001:db8:1:2::1") == visitor_network("2001:db8:1:2:ffff::9") == "2001:db8:1:2::/64"
    assert visitor_network("2001:db8:1:3::1") != visitor_network("2001:db8:1:2::1")
    assert visitor_network("::ffff:192.0.2.1") == visitor_network("192.0.2.1") == "192.0.2.1"
    assert ask(visitor("2001:db8:1:2::1")).status_code == 200
    assert ask(visitor("2001:db8:1:2::2")).status_code == 200
    assert ask(visitor("2001:db8:1:2::3")).status_code == 429


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
def test_no_raw_ip_in_the_database_or_scouts_logs(demo, caplog):
    # (Uvicorn's own access log is switched off in the Procfile with --no-access-log.)
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


def test_a_question_without_a_cookie_is_refused_before_it_counts(demo):
    no_cookies = TestClient(app, headers={"X-Real-IP": "192.0.2.40"})
    refused = ask(no_cookies)
    assert refused.status_code == 400
    assert "cookie" in refused.json()["detail"]
    assert jobs_in_database() == 0


def test_jobs_from_before_the_demo_stay_private(demo):
    old_job = store.create_job("A question asked before the demo existed")  # has no visitor ID
    assert TestClient(app).get(f"/api/research/{old_job}").status_code == 404
    assert visitor().get(f"/api/research/{old_job}").status_code == 404


def test_visitors_never_see_api_error_details(demo):
    class Broken:
        class messages:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("Your credit balance is too low (billing details)")

    llm.set_client(Broken())
    browser = visitor()
    job = browser.get(f"/api/research/{ask(browser).json()['id']}").json()
    assert job["status"] == "failed"
    assert "billing" not in job["error"] and "Something went wrong" in job["error"]


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


def test_fingerprints_are_wiped_after_their_day(demo, monkeypatch):
    pretend_it_is(monkeypatch, datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc))
    ask(visitor())
    pretend_it_is(monkeypatch, datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc))
    with TestClient(app):
        pass
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM jobs WHERE ip_hash IS NOT NULL").fetchone()[0] == 0


def test_questions_left_running_by_a_restart_are_marked_failed(demo):
    job_id = store.try_create_job(QUESTION, daily_limit=10)[0]  # still "running"
    with TestClient(app):  # Scout starts again
        pass
    job = store.get_job(job_id)
    assert job["status"] == "failed" and "restarted" in job["error"]


# ---------------------------------------------------------------- cheaper effort
def slowed_down(seconds, agent):
    """The pretend Claude, but the given agent ("planner" or "writer") takes this many seconds."""
    client = FakeClient()
    answer = client.messages.create

    def create(**kwargs):
        tools = [t.get("name") for t in kwargs.get("tools", [])]
        if (agent == "planner" and tools == ["submit_plan"]) or (agent == "writer" and not tools):
            time.sleep(seconds)
        return answer(**kwargs)

    client.messages.create = create
    return client


def test_time_limit_stops_before_research_starts():
    llm.set_client(slowed_down(0.3, "planner"))
    with pytest.raises(TimeoutError):
        run_research(QUESTION, time_limit=0.1)


def test_time_limit_keeps_a_report_that_has_been_paid_for():
    client = slowed_down(0.3, "writer")
    llm.set_client(client)
    progress = []
    state = run_research(QUESTION, on_progress=progress.append, time_limit=0.1)
    assert "## Sources" in state["report"]                     # the finished report is kept
    reviews = [c for c in client.messages.calls if [t.get("name") for t in c.get("tools", [])] == ["submit_review"]]
    assert reviews == []                                         # and the fact-check is skipped
    assert progress[-1].startswith("Out of time")


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


def test_demo_starts_with_a_salt_and_a_database(tmp_path):
    result = run_python("import scout.server", DEMO_MODE="1", SCOUT_IP_SALT="a-long-random-test-salt",
                        SCOUT_DB=str(tmp_path / "demo.db"))
    assert result.returncode == 0, result.stderr


def test_demo_refuses_to_start_without_a_database_setting():
    result = run_python("import scout.server", DEMO_MODE="1", SCOUT_IP_SALT="a-long-random-test-salt", SCOUT_DB="")
    assert result.returncode != 0
    assert "SCOUT_DB" in result.stderr


def test_a_mistyped_demo_mode_refuses_to_start():
    result = run_python("import scout.config", DEMO_MODE="ture")
    assert result.returncode != 0
    assert "DEMO_MODE must be 1 (on) or 0 (off)" in result.stderr


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
