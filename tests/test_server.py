from fastapi.testclient import TestClient

from scout import config
from scout.server import app

client = TestClient(app)


def test_question_runs_to_a_report():
    started = client.post("/api/research", json={"question": "What are facts A and B?"})
    assert started.status_code == 200
    job = client.get(f"/api/research/{started.json()['id']}").json()
    assert job["status"] == "done"
    assert "## Sources" in job["report"]
    assert client.get("/api/history").json()[0]["id"] == started.json()["id"]


def test_short_question_is_rejected():
    assert client.post("/api/research", json={"question": "hi"}).status_code == 400


def test_password_protects_the_app(monkeypatch):
    monkeypatch.setattr(config, "PASSWORD", "s3cret")
    assert client.get("/api/history").status_code == 401
    assert client.get("/api/history", auth=("scout", "s3cret")).status_code == 200
    assert client.get("/health").status_code == 200


def test_daily_limit(monkeypatch):
    monkeypatch.setattr(config, "DAILY_LIMIT", 1)
    assert client.post("/api/research", json={"question": "What are facts A and B?"}).status_code == 200
    assert client.post("/api/research", json={"question": "What are facts A and B?"}).status_code == 429
