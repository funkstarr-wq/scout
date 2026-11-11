from scout import config
from scout.agents import check_citations
from scout.tools import handle_record_finding

GOOD = {"claim": "The bridge opened in 1937.", "source_url": "https://example.org/bridge", "source_title": "Bridge"}


def test_good_finding_is_saved():
    findings = []
    message = handle_record_finding(GOOD, findings, "Bridge history")
    assert message.startswith("Saved finding 1")
    assert findings[0]["source_url"] == "https://example.org/bridge"


def test_bad_url_gets_a_helpful_error():
    findings = []
    message = handle_record_finding({**GOOD, "source_url": "example.org"}, findings, "t")
    assert "must be a full web address" in message
    assert findings == []


def test_duplicate_is_refused():
    findings = []
    handle_record_finding(GOOD, findings, "t")
    assert "already recorded" in handle_record_finding(GOOD, findings, "t")


def test_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(config, "MAX_FINDINGS_PER_RESEARCHER", 1)
    findings = []
    handle_record_finding(GOOD, findings, "t")
    other = {**GOOD, "claim": "A different fact about the bridge."}
    assert "limit" in handle_record_finding(other, findings, "t")


def test_citation_check_catches_missing_sources():
    sources = [{"n": 1}, {"n": 2}]
    assert check_citations("Fact [1]. Fact [2].", sources) == []
    assert check_citations("No citations here.", sources)
    assert "[7]" in check_citations("Fact [7].", sources)[0]


def test_ask_for_tool_reminds_claude_once():
    from scout import llm
    from scout.agents import ask_for_tool
    from tests.fake_llm import reply, text_block, tool_block

    class Chatty:
        def __init__(self):
            self.replies = [reply([text_block("Here is my plan in prose.")]),
                            reply([tool_block("submit_plan", {"subtasks": []})], "tool_use")]

        def create(self, **kwargs):
            return self.replies.pop(0)

    llm.set_client(type("C", (), {"messages": Chatty()})())
    assert ask_for_tool("m", "s", {"name": "submit_plan"}, "q") == {"subtasks": []}
