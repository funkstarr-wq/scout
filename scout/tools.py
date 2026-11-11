"""The tools Scout's agents can use.

A tool is a description Claude reads (name, purpose, inputs) plus, for
our own tools, a small Python function that does the work when Claude
calls it. The descriptions matter as much as the code: Claude decides
when and how to use a tool from its description alone.
"""
from urllib.parse import urlparse

from . import config

# Web search runs on Anthropic's servers. We only describe it; Claude
# performs the searches itself and the results come back in its reply.
WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": config.MAX_SEARCHES_PER_RESEARCHER,
}

RECORD_FINDING_TOOL = {
    "name": "record_finding",
    "description": (
        "Save one fact you found during research so it can be used in the final report. "
        "Call this once per fact, as soon as you find it. Only recorded findings reach the "
        "report; anything not recorded is lost. Do not record opinions or guesses, and do "
        "not record the same fact twice."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "claim": {
                "type": "string",
                "description": (
                    "The fact, written as one complete sentence in your own words that makes "
                    "sense without any other context. Include names, numbers and dates. "
                    "Example: 'The Golden Gate Bridge opened to traffic on 28 May 1937.'"
                ),
            },
            "source_url": {
                "type": "string",
                "description": "The full web address (starting with https://) of the page that states this fact.",
            },
            "source_title": {
                "type": "string",
                "description": "The title of that page, or the name of the organisation that published it.",
            },
        },
        "required": ["claim", "source_url", "source_title"],
    },
}

SUBMIT_PLAN_TOOL = {
    "name": "submit_plan",
    "description": "Submit the research plan: the list of independent research tasks for the researchers.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subtasks": {
                "type": "array",
                "minItems": 1,
                "maxItems": config.MAX_SUBTASKS,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "A short name for the task, three to six words."},
                        "objective": {"type": "string", "description": "Exactly what to find out, and what is out of scope."},
                        "search_hints": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Two or three short starting search phrases.",
                        },
                    },
                    "required": ["title", "objective", "search_hints"],
                },
            }
        },
        "required": ["subtasks"],
    },
}

SUBMIT_REVIEW_TOOL = {
    "name": "submit_review",
    "description": "Submit your verdict on the draft report.",
    "input_schema": {
        "type": "object",
        "properties": {
            "approved": {"type": "boolean", "description": "true if the report can be published as it is."},
            "problems": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific problems for the writer to fix. Empty if approved.",
            },
        },
        "required": ["approved", "problems"],
    },
}


def handle_record_finding(tool_input: dict, findings: list, subtask_title: str) -> str:
    """Runs when a researcher calls record_finding.

    Returns a short message that Claude reads. Error messages say exactly
    what was wrong and how to fix it, so the agent can correct itself.
    """
    claim = (tool_input.get("claim") or "").strip()
    url = (tool_input.get("source_url") or "").strip()
    title = (tool_input.get("source_title") or "").strip() or url

    if len(claim) < 15:
        return "Not saved: the claim is missing or too short. Write the fact as one complete sentence."
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return (
            "Not saved: source_url must be a full web address starting with https://, "
            f"for example https://www.example.org/page. You sent: {url!r}"
        )
    if len(findings) >= config.MAX_FINDINGS_PER_RESEARCHER:
        return (
            f"Not saved: you have already recorded {len(findings)} findings, which is the limit. "
            "Stop searching and write your one or two sentence summary now."
        )
    if any(f["claim"].lower() == claim.lower() for f in findings):
        return "Not saved: you already recorded this exact claim."

    findings.append({"claim": claim, "source_url": url, "source_title": title, "subtask": subtask_title})
    remaining = config.MAX_FINDINGS_PER_RESEARCHER - len(findings)
    return f"Saved finding {len(findings)}. You can record up to {remaining} more."
