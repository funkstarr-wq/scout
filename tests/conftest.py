import pytest

from scout import config, llm
from tests.fake_llm import FakeClient


@pytest.fixture(autouse=True)
def fake_claude(tmp_path, monkeypatch):
    """Every test gets a pretend Claude, its own empty database, and the live demo switched off."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(config, "PASSWORD", "")
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(config, "FAKE_MODE", False)
    monkeypatch.setattr(config, "LIVE_QUESTIONS", True)
    client = FakeClient()
    llm.set_client(client)
    yield client
    llm.set_client(None)


@pytest.fixture
def demo(monkeypatch):
    """Switch on the live demo, taking visitors' own questions, with a salt and generous limits
    that each test can tighten. (The real demo takes none unless SCOUT_LIVE_QUESTIONS=1.)"""
    from scout import server

    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "IP_SALT", "test-salt-for-the-demo")
    monkeypatch.setattr(config, "DAILY_LIMIT", 50)
    monkeypatch.setattr(config, "PER_VISITOR_LIMIT", 2)
    monkeypatch.setattr(config, "MAX_CONCURRENT", 1)
    monkeypatch.setattr(server.slots, "running", 0)
