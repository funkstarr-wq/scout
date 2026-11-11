import pytest

from scout import config, llm
from tests.fake_llm import FakeClient


@pytest.fixture(autouse=True)
def fake_claude(tmp_path, monkeypatch):
    """Every test gets a pretend Claude and its own empty database."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(config, "PASSWORD", "")
    client = FakeClient()
    llm.set_client(client)
    yield client
    llm.set_client(None)
