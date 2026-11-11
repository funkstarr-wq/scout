"""Scout's workflow, drawn as a LangGraph graph.

    START -> plan -> research (one copy per task, in parallel) -> write -> review
                                                                   ^        |
                                                                   +--------+  (if rejected)
"""
import operator
from typing import Annotated, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from . import agents, config


class ScoutState(TypedDict, total=False):
    question: str
    subtasks: list[dict]
    findings: Annotated[list[dict], operator.add]  # each researcher ADDS to this list
    report: str
    sources: list[dict]
    review: dict
    revisions: int


class ResearchJob(TypedDict):
    question: str
    subtask: dict


def plan_node(state: ScoutState) -> dict:
    return {"subtasks": agents.plan_research(state["question"]), "revisions": 0}


def send_to_researchers(state: ScoutState) -> list[Send]:
    # One Send per task: LangGraph runs all the research nodes at the same time.
    return [Send("research", {"question": state["question"], "subtask": t}) for t in state["subtasks"]]


def research_node(job: ResearchJob) -> dict:
    return {"findings": agents.research_subtask(job["question"], job["subtask"])}


def write_node(state: ScoutState) -> dict:
    feedback = state["review"]["problems"] if state.get("review") else None
    report, sources = agents.write_report(state["question"], state["findings"], feedback)
    return {"report": report, "sources": sources}


def review_node(state: ScoutState) -> dict:
    review = agents.review_report(state["question"], state["report"], state["findings"], state["sources"])
    return {"review": review, "revisions": state.get("revisions", 0) + 1}


def after_review(state: ScoutState) -> str:
    if state["review"]["approved"] or state["revisions"] > config.MAX_REVISIONS:
        return END
    return "write"


def build_graph():
    builder = StateGraph(ScoutState)
    builder.add_node("plan", plan_node)
    builder.add_node("research", research_node)
    builder.add_node("write", write_node)
    builder.add_node("review", review_node)

    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", send_to_researchers, ["research"])
    builder.add_edge("research", "write")
    builder.add_edge("write", "review")
    builder.add_conditional_edges("review", after_review, ["write", END])
    return builder.compile()


graph = build_graph()


def describe(node: str, update: dict) -> str:
    """Turn a graph step into a short progress message for the web page."""
    if node == "plan":
        titles = "; ".join(t["title"] for t in update["subtasks"])
        return f"Planned {len(update['subtasks'])} research task(s): {titles}"
    if node == "research":
        return f"A researcher finished with {len(update['findings'])} finding(s)"
    if node == "write":
        return "Wrote a draft report"
    if node == "review":
        if update["review"]["approved"]:
            return "Fact-checker approved the report"
        return f"Fact-checker asked for {len(update['review']['problems'])} fix(es)"
    return node


def run_research(question: str, on_progress: Callable[[str], None] | None = None) -> dict:
    """Run the whole graph for one question and return the final state."""
    state: dict = {"question": question, "findings": []}
    for step in graph.stream({"question": question, "findings": []}, stream_mode="updates"):
        for node, update in step.items():
            if not update:
                continue
            if node == "research":
                state["findings"] = state["findings"] + update["findings"]
            else:
                state.update(update)
            if on_progress:
                on_progress(describe(node, update))
    return state
