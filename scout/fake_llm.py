"""A pretend Claude. It gives scripted answers, so tests (and SCOUT_FAKE=1) are fast, free and repeatable."""
from types import SimpleNamespace as NS


def text_block(text):
    return NS(type="text", text=text)


def tool_block(name, tool_input, block_id="toolu_1"):
    return NS(type="tool_use", name=name, input=tool_input, id=block_id)


def reply(blocks, stop_reason="end_turn"):
    return NS(content=blocks, stop_reason=stop_reason)


class FakeMessages:
    def __init__(self, approve=True):
        self.calls = []
        self.approve = approve

    def create(self, **kwargs):
        self.calls.append(kwargs)
        tool_names = [t.get("name") for t in kwargs.get("tools", [])]
        # The only tool offered tells us which agent is calling.
        forced = tool_names[0] if len(tool_names) == 1 else None

        if forced == "submit_plan":
            return reply([tool_block("submit_plan", {"subtasks": [
                {"title": "Part A", "objective": "Find fact A.", "search_hints": ["fact a"]},
                {"title": "Part B", "objective": "Find fact B.", "search_hints": ["fact b"]},
            ]})], "tool_use")

        if forced == "submit_review":
            if self.approve:
                return reply([tool_block("submit_review", {"approved": True, "problems": []})], "tool_use")
            return reply([tool_block("submit_review", {"approved": False, "problems": ["Cite [2] in paragraph one."]})], "tool_use")

        if forced == "submit_grade":
            scores = {k: 0.8 for k in ["factual_accuracy", "citation_accuracy", "completeness", "source_quality", "clarity"]}
            return reply([tool_block("submit_grade", {**scores, "comment": "Fine."})], "tool_use")

        if "record_finding" in tool_names:
            # First turn: record a finding. Second turn: finish.
            already_recorded = any(m["role"] == "user" and isinstance(m["content"], list) for m in kwargs["messages"])
            if not already_recorded:
                task = kwargs["messages"][0]["content"]
                letter = "A" if "Part A" in task else "B"
                return reply([tool_block("record_finding", {
                    "claim": f"Fact {letter} is true according to the source.",
                    "source_url": f"https://example.org/{letter.lower()}",
                    "source_title": f"Example {letter}",
                })], "tool_use")
            return reply([text_block("Found what I needed.")])

        # Otherwise this is the writer.
        return reply([text_block("<report>Fact A is true [1]. Fact B is true [2].</report>")])


class FakeClient:
    def __init__(self, approve=True):
        self.messages = FakeMessages(approve)
