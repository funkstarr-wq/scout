"""Tests for the saved questions: recording them once, and replaying them on the demo page for free."""
import pytest
from fastapi.testclient import TestClient

from scout import config, examples, llm, store
from scout.server import app, recorder

client = TestClient(app)
ADMIN = ("admin", "long-admin-password")


class NoClaudeAllowed:
    """Fails the test if anything tries to call Claude."""

    class messages:
        @staticmethod
        def create(**kwargs):
            raise AssertionError("A replay must never call the Claude API")


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "long-admin-password")


@pytest.fixture
def no_files(tmp_path, monkeypatch):
    """Pretend the project holds no saved JSON files, so only the database counts."""
    monkeypatch.setattr(examples, "EXAMPLES_DIR", tmp_path)


def press(which, check=None):
    """Press a button on the recordings page, then wait for the recording to finish."""
    from scout.server import recording_check

    form = {"which": which, "check": recording_check() if check is None else check}
    response = client.post("/admin/recordings", data=form, auth=ADMIN, follow_redirects=False)
    if recorder.thread is not None:
        recorder.thread.join(timeout=30)
    return response


# ------------------------------------------------------------ recording
def test_recording_keeps_every_step_with_its_time(no_files):
    run = examples.record("coffee-and-sleep")
    assert run["question"] == examples.EXAMPLES["coffee-and-sleep"]
    assert "## Sources" in run["report"]
    times = [step["at"] for step in run["timeline"]]
    assert times == sorted(times) and times[-1] <= run["took_seconds"]
    assert [step["message"] for step in run["timeline"]] == run["progress"]
    assert run["progress"][0].startswith("Planned")


def test_a_run_in_the_database_is_used_and_marked_as_ready(no_files):
    assert examples.recorded() == []
    store.save_recording("heat-pumps-vs-gas-boilers", {"question": "q", "report": "r", "progress": []})
    assert examples.load("heat-pumps-vs-gas-boilers")["report"] == "r"
    assert examples.recorded() == ["heat-pumps-vs-gas-boilers"]
    ready = {e["name"]: e["recorded"] for e in client.get("/api/settings").json()["examples"]}
    assert ready["heat-pumps-vs-gas-boilers"] is True
    assert ready["coffee-and-sleep"] is False


def test_only_listed_names_can_be_saved_runs(no_files):
    store.save_recording("not-a-preset", {"report": "sneaky"})
    assert examples.load("not-a-preset") is None
    assert client.get("/api/examples/not-a-preset").status_code == 404


# ------------------------------------------------------------ replaying
def test_replaying_costs_nothing_and_uses_no_question(demo, no_files, monkeypatch):
    store.save_recording("coffee-and-sleep", examples.record("coffee-and-sleep"))
    spent = store.spend_this_month()
    llm.set_client(NoClaudeAllowed())
    monkeypatch.setattr(config, "PER_VISITOR_LIMIT", 1)
    for _ in range(5):
        assert client.get("/api/examples/coffee-and-sleep").status_code == 200
    assert store.count_jobs_today() == 0
    assert store.spend_this_month() == spent


def test_demo_page_offers_the_saved_questions():
    page = client.get("/demo").text
    for piece in ('id="saved-pick"', 'id="watch"', "Skip to the report", "#saved-", "/api/examples/"):
        assert piece in page


# ------------------------------------------------------- the owner's page
def test_recordings_page_needs_the_admin_password(no_files, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "")
    assert client.get("/admin/recordings", auth=ADMIN).status_code == 404
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "long-admin-password")
    assert client.get("/admin/recordings").status_code == 401
    assert client.get("/admin/recordings", auth=("admin", "wrong")).status_code == 401
    page = client.get("/admin/recordings", auth=ADMIN)
    assert page.status_code == 200
    for question in examples.EXAMPLES.values():
        assert question.replace("'", "&#x27;") in page.text
    assert "Record the 6 missing questions" in page.text


def test_the_record_button_records_the_missing_questions(admin, no_files):
    store.save_recording("coffee-and-sleep", {"report": "already saved"})
    response = press("missing")
    assert response.status_code == 303
    assert examples.load("coffee-and-sleep")["report"] == "already saved"  # left alone
    assert examples.recorded() == list(examples.EXAMPLES)
    assert examples.load("heat-pumps-vs-gas-boilers")["timeline"]
    assert "Watch it" in client.get("/admin/recordings", auth=ADMIN).text


def test_the_record_button_needs_the_pages_own_check_code(admin, no_files):
    """Stops another website pressing the button for a signed-in owner."""
    assert press("all", check="guess").status_code == 403
    assert press("all", check="").status_code == 403
    assert examples.recorded() == []


def test_recording_stops_when_the_months_budget_is_used(demo, admin, no_files, monkeypatch):
    monkeypatch.setattr(config, "MONTHLY_BUDGET_USD", 1.0)
    store.add_spend(0.80)
    llm.set_client(NoClaudeAllowed())  # nothing may be spent
    assert press("all").status_code == 303
    assert examples.recorded() == []
    assert "budget is used up" in client.get("/admin/recordings", auth=ADMIN).text


# ------------------------------------------------- saved questions only
def test_the_real_demo_takes_no_questions_of_its_own_unless_switched_on():
    from tests.test_demo import run_python

    code = "from scout import config; print(config.LIVE_QUESTIONS)"
    assert run_python(code, DEMO_MODE="1", SCOUT_LIVE_QUESTIONS="").stdout.strip() == "False"
    assert run_python(code, DEMO_MODE="1", SCOUT_LIVE_QUESTIONS="1").stdout.strip() == "True"
    assert run_python(code, DEMO_MODE="0", SCOUT_LIVE_QUESTIONS="").stdout.strip() == "True"  # your own copy
    typo = run_python(code, DEMO_MODE="1", SCOUT_LIVE_QUESTIONS="maybe")
    assert typo.returncode != 0 and "SCOUT_LIVE_QUESTIONS must be 1 (on) or 0 (off)" in typo.stderr


def test_with_live_questions_off_nothing_can_be_asked_or_spent(demo, no_files, monkeypatch):
    monkeypatch.setattr(config, "LIVE_QUESTIONS", False)
    llm.set_client(NoClaudeAllowed())
    page = client.get("/demo")
    assert "scout_visitor" not in page.headers.get("set-cookie", "")  # nothing to remember about visitors
    assert client.get("/api/settings").json()["live"] is False
    response = client.post("/api/research", json={"question": "Does drinking coffee affect sleep?"})
    assert response.status_code == 403
    assert "saved questions only" in response.json()["detail"]
    assert store.count_jobs_today() == 0
    assert store.spend_this_month() == 0


def test_the_page_hides_the_question_box_until_live_questions_are_on():
    page = client.get("/demo").text
    assert '<form id="ask" class="card" hidden>' in page
    assert 'id="saved-banner"' in page and 'id="no-saved"' in page
