"""Scout's four agents: the planner, the researchers, the writer and the reviewer."""
import re
import time

from . import config, llm
from .prompts import load_prompt
from .tools import (
    RECORD_FINDING_TOOL,
    SUBMIT_PLAN_TOOL,
    SUBMIT_REVIEW_TOOL,
    WEB_SEARCH_TOOL,
    handle_record_finding,
)


def ask_for_tool(model: str, system: str, tool: dict, content: str, max_tokens: int = 4000) -> dict:
    """Ask Claude to answer by calling one tool, and return what it passed to that tool.

    Some newer models don't allow tool_choice to force a particular tool, so we
    ask for it in the prompt and check the reply. If Claude answers in prose
    instead, we remind it once.
    """
    messages = [{"role": "user", "content": content}]
    for _attempt in range(2):
        response = llm.client().messages.create(
            model=model, max_tokens=max_tokens, system=system, tools=[tool], messages=messages
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == tool["name"]:
                return block.input
        messages += [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": f"Please give your answer by calling the {tool['name']} tool."},
        ]
    raise RuntimeError(f"Claude did not call {tool['name']}")


def _text(response) -> str:
    return "".join(block.text for block in response.content if block.type == "text")


# ---------------------------------------------------------------- planner
def plan_research(question: str) -> list[dict]:
    """Split the question into independent research tasks."""
    plan = ask_for_tool(
        config.LEAD_MODEL, load_prompt("planner"), SUBMIT_PLAN_TOOL, f"<question>{question}</question>"
    )
    subtasks = plan.get("subtasks", [])
    if not subtasks:
        raise RuntimeError("The planner returned an empty plan")
    return subtasks[: config.MAX_SUBTASKS]


# ------------------------------------------------------------- researcher
def research_subtask(question: str, subtask: dict, deadline: float | None = None) -> list[dict]:
    """One researcher: an agent in a loop with web_search and record_finding.

    If a deadline is given (a time.monotonic() value), the researcher stops
    taking new turns once it has passed and hands in what it has found so far.
    """
    findings: list[dict] = []
    hints = ", ".join(subtask.get("search_hints", []))
    messages = [
        {
            "role": "user",
            "content": (
                f"<overall_question>{question}</overall_question>\n"
                f"<your_task title=\"{subtask['title']}\">\n{subtask['objective']}\n</your_task>\n"
                f"<search_hints>{hints}</search_hints>"
            ),
        }
    ]

    for _turn in range(config.MAX_RESEARCH_TURNS):
        if deadline is not None and time.monotonic() > deadline:
            break  # out of time: keep what we have rather than spend more
        response = llm.client().messages.create(
            model=config.WORKER_MODEL,
            max_tokens=4000,
            system=load_prompt("researcher"),
            tools=[WEB_SEARCH_TOOL, RECORD_FINDING_TOOL],
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            # Claude wants to use one of OUR tools. Run it and send back the result.
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if block.name == "record_finding":
                    output = handle_record_finding(block.input, findings, subtask["title"])
                else:
                    output = f"Unknown tool: {block.name}"
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
            messages.append({"role": "user", "content": results})
            continue

        if response.stop_reason == "pause_turn":
            # A long server-side search paused. Sending the conversation back lets it carry on.
            continue

        break  # "end_turn" (finished) or "max_tokens"

    return findings


# ----------------------------------------------------------------- writer
def number_sources(findings: list[dict]) -> list[dict]:
    """Give every distinct web page a number, in the order it was found."""
    sources: list[dict] = []
    seen: dict[str, int] = {}
    for f in findings:
        if f["source_url"] not in seen:
            seen[f["source_url"]] = len(sources) + 1
            sources.append({"n": len(sources) + 1, "url": f["source_url"], "title": f["source_title"]})
        f["source_n"] = seen[f["source_url"]]
    return sources


def format_findings(findings: list[dict]) -> str:
    lines = [f'<finding source="[{f["source_n"]}]">{f["claim"]}</finding>' for f in findings]
    return "<findings>\n" + "\n".join(lines) + "\n</findings>"


def write_report(question: str, findings: list[dict], feedback: list[str] | None = None) -> tuple[str, list[dict]]:
    """Turn findings into a cited Markdown report. Returns (report, sources)."""
    sources = number_sources(findings)
    if not findings:
        return ("Scout could not find reliable information to answer this question.", [])

    content = f"<question>{question}</question>\n{format_findings(findings)}"
    if feedback:
        content += "\n<reviewer_feedback>\n" + "\n".join(f"- {p}" for p in feedback) + "\n</reviewer_feedback>"
        content += "\nRewrite the report to fix every problem the reviewer listed."

    response = llm.client().messages.create(
        model=config.LEAD_MODEL,
        max_tokens=config.WRITER_MAX_TOKENS,
        system=load_prompt("writer"),
        messages=[{"role": "user", "content": content}],
    )
    text = _text(response)
    match = re.search(r"<report>(.*?)</report>", text, re.DOTALL)
    body = (match.group(1) if match else text).strip()

    source_list = "\n".join(f"{s['n']}. [{s['title']}]({s['url']})" for s in sources)
    return f"{body}\n\n## Sources\n\n{source_list}\n", sources


# --------------------------------------------------------------- reviewer
def check_citations(report: str, sources: list[dict]) -> list[str]:
    """Checks a computer can do without an AI: do the citations point at real sources?"""
    body = report.split("## Sources")[0]
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", body)}
    problems = []
    if sources and not cited:
        problems.append("The report has no citations. Every factual sentence needs one, like [1].")
    bad = sorted(n for n in cited if n < 1 or n > len(sources))
    if bad:
        problems.append(f"These citation numbers do not match any source: {bad}. Use 1 to {len(sources)} only.")
    return problems


def review_report(question: str, report: str, findings: list[dict], sources: list[dict]) -> dict:
    """The evaluator half of the evaluator-optimizer loop."""
    problems = check_citations(report, sources)
    if not sources:
        return {"approved": True, "problems": []}
    number_sources(findings)  # make sure every finding carries its source number

    verdict = ask_for_tool(
        config.LEAD_MODEL,
        load_prompt("reviewer"),
        SUBMIT_REVIEW_TOOL,
        f"<question>{question}</question>\n{format_findings(findings)}\n<draft>\n{report}\n</draft>",
    )
    problems += list(verdict.get("problems", []))
    return {"approved": bool(verdict.get("approved")) and not problems, "problems": problems}
