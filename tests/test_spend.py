"""Tests for the live demo's monthly budget. No real API calls: the pretend Claude reports usage."""
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from scout import config, llm, spend, store
from scout.server import app
from tests.fake_llm import FakeClient

ROOT = Path(__file__).resolve().parent.parent


def usage(tokens_in=0, tokens_out=0, searches=0, cache_write=0, cache_read=0):
    return NS(input_tokens=tokens_in, output_tokens=tokens_out, cache_creation_input_tokens=cache_write,
              cache_read_input_tokens=cache_read, server_tool_use=NS(web_search_requests=searches))


def visitor(ip="203.0.113.60"):
    browser = TestClient(app, headers={"X-Real-IP": ip})
    browser.get("/demo")
    return browser


# --------------------------------------------------------------- pricing
def test_prices_each_model_per_million_tokens():
    assert spend.cost_of("claude-sonnet-5-5", usage(1_000_000, 1_000_000)) == pytest.approx(12.00)
    assert spend.cost_of("claude-haiku-5-5", usage(50_000, 1_000_000)) == pytest.approx(0.505)  # $0.10 in, $0.50 out


def test_long_haiku_prompts_cost_more():
    assert spend.cost_of("claude-haiku-5-5", usage(200_000, 0)) == pytest.approx(0.10)   # 200k x $0.50 per million


def test_web_searches_and_caching_are_counted():
    assert spend.cost_of("claude-haiku-5-5", usage(searches=3)) == pytest.approx(0.03)
    assert spend.cost_of("claude-sonnet-5-5", usage(cache_write=1_000_000, cache_read=1_000_000)) == pytest.approx(2.70)


def test_an_unknown_model_is_priced_high_so_the_demo_stops_early():
    assert spend.cost_of("some-future-model", usage(1_000_000, 0)) > spend.cost_of("claude-sonnet-5-5", usage(1_000_000, 0))


def test_a_reply_without_usage_costs_nothing():
    assert spend.cost_of("claude-sonnet-5-5", None) == 0.0


# ------------------------------------------------------------ recording
def test_every_reply_is_added_to_the_months_total():
    fake = FakeClient()
    answer = fake.messages.create

    def create(**kwargs):  # the pretend Claude, now reporting usage like the real one
        reply = answer(**kwargs)
        reply.usage = usage(10_000, 1_000, searches=1)
        return reply

    fake.messages.create = create
    llm.set_client(spend.Metered(fake))
    from scout.graph import run_research
    run_research("What are facts A and B?")
    calls = len(fake.messages.calls)
    assert calls > 0
    assert store.spend_this_month() > 0.01 * calls  # each call ran one search at least


def test_a_failing_meter_never_breaks_a_question(monkeypatch):
    monkeypatch.setattr(store, "add_spend", lambda usd: (_ for _ in ()).throw(RuntimeError("disk full")))
    metered = spend.Metered(FakeClient())
    reply = metered.messages.create(model="claude-sonnet-5-5", tools=[{"name": "submit_plan"}], messages=[])
    assert reply.content


# ---------------------------------------------------------- the budget
def test_demo_stops_before_the_budget_is_reached(demo, monkeypatch):
    monkeypatch.setattr(config, "MONTHLY_BUDGET_USD", 10.0)
    store.add_spend(9.60)  # less than one question's headroom left
    refused = visitor().post("/api/research", json={"question": "What are facts A and B?"})
    assert refused.status_code == 429
    assert "this month's research budget" in refused.json()["detail"]
    with store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_demo_takes_questions_while_there_is_budget_left(demo, monkeypatch):
    monkeypatch.setattr(config, "MONTHLY_BUDGET_USD", 10.0)
    store.add_spend(5.00)
    assert visitor().post("/api/research", json={"question": "What are facts A and B?"}).status_code == 200


def test_budget_resets_each_month(demo, monkeypatch):
    monkeypatch.setattr(config, "MONTHLY_BUDGET_USD", 10.0)
    monkeypatch.setattr(store, "utcnow", lambda: datetime(2026, 11, 30, 22, 0, tzinfo=timezone.utc))
    store.add_spend(10.00)
    assert visitor("198.51.100.80").post("/api/research", json={"question": "What are facts A and B?"}).status_code == 429
    monkeypatch.setattr(store, "utcnow", lambda: datetime(2026, 12, 1, 0, 5, tzinfo=timezone.utc))
    assert store.spend_this_month() == 0.0
    assert visitor("198.51.100.81").post("/api/research", json={"question": "What are facts A and B?"}).status_code == 200


def test_your_own_copy_has_no_budget(monkeypatch):
    monkeypatch.setattr(config, "MONTHLY_BUDGET_USD", 10.0)
    store.add_spend(50.00)
    assert TestClient(app).post("/api/research", json={"question": "What are facts A and B?"}).status_code == 200


def test_a_mistyped_budget_refuses_to_start():
    env = {**os.environ, "PYTHONPATH": str(ROOT), "SCOUT_MONTHLY_BUDGET_USD": "ten dollars"}
    result = subprocess.run([sys.executable, "-c", "import scout.config"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "SCOUT_MONTHLY_BUDGET_USD must be an amount in US dollars" in result.stderr


# ------------------------------------------------------ the owner's page
def test_spend_page_needs_the_admin_password(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "")
    assert client.get("/admin/spend").status_code == 404
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "long-admin-password")
    monkeypatch.setattr(config, "MONTHLY_BUDGET_USD", 10.0)
    assert client.get("/admin/spend", follow_redirects=False).headers["location"] == "/admin/login?next=/admin/spend"
    store.add_spend(2.5)
    page = client.get("/admin/spend", auth=("admin", "long-admin-password")).json()
    assert page["spent_usd"] == 2.5 and page["budget_usd"] == 10.0 and page["accepting_questions"] is True
