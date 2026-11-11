from scout import llm
from scout.graph import run_research
from tests.fake_llm import FakeClient


def test_full_run_produces_cited_report():
    progress = []
    state = run_research("What are facts A and B?", on_progress=progress.append)

    assert len(state["subtasks"]) == 2
    assert len(state["findings"]) == 2          # one from each parallel researcher
    assert "[1]" in state["report"] and "## Sources" in state["report"]
    assert "https://example.org/a" in state["report"]
    assert state["review"]["approved"] is True
    assert progress[0].startswith("Planned 2 research task(s)")


def test_rejected_report_is_rewritten_once():
    client = FakeClient(approve=False)
    llm.set_client(client)
    state = run_research("What are facts A and B?")

    writer_calls = [c for c in client.messages.calls if not c.get("tools")]
    assert len(writer_calls) == 2                 # first draft plus one revision
    assert "reviewer_feedback" in writer_calls[1]["messages"][0]["content"]
    assert state["revisions"] == 2
