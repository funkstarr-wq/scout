"""The saved questions: finished runs of Scout that anyone can read or replay for free.

Each one is researched once, for real, and saved with its report and a timed log of
every step. After that, showing it never calls the Claude API, so it costs nothing
however many people look:

- /examples/<name> shows the finished report (the website's cards link to the first three).
- The demo page's "Watch a saved question" list replays the run step by step, at its real pace.

There are two ways to make them. The owner can press the button on /admin/recordings,
which runs them on the live site and keeps them in its database; or run
scripts/make_examples.py on their own computer, which saves JSON files in
scout/static/examples/ to commit. A run in the database is used first.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import config, store

EXAMPLES_DIR = Path(__file__).resolve().parent / "static" / "examples"
CENTS_PER_RUN = 10  # a rough estimate with the demo's settings; /admin/spend shows the real figures

# The first three match the example cards on the website.
EXAMPLES = {
    "coffee-and-sleep": "Does drinking coffee affect how well you sleep?",
    "heat-pumps-vs-gas-boilers": "How do heat pumps compare with gas boilers for a typical UK home?",
    "four-day-week-trials": "What did the UK's four-day working week trials find?",
    "exercise-each-week": "How much exercise do adults need each week to stay healthy?",
    "electric-cars-lifetime": "Are electric cars greener than petrol cars over their whole lifetime?",
    "ai-agents-at-work": "What are AI agents, and how are businesses starting to use them?",
}


def load(name: str) -> dict | None:
    """The saved run, or None if the name is unknown or it hasn't been made yet."""
    if name not in EXAMPLES:  # only these exact names, so a name can never point elsewhere
        return None
    saved = store.get_recording(name)
    if saved is not None:
        return saved
    try:
        return json.loads((EXAMPLES_DIR / f"{name}.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def recorded() -> list[str]:
    """The names that have a saved run, in the order above."""
    in_database = store.recording_dates()
    return [n for n in EXAMPLES if n in in_database or (EXAMPLES_DIR / f"{n}.json").is_file()]


def record(name: str, on_progress: Callable[[str], None] | None = None) -> dict:
    """Research one saved question for real (this costs money) and return the run, ready to save.

    Each progress message is kept with the number of seconds since the start, so the
    demo page can replay the run at its real pace.
    """
    from .graph import run_research  # loaded here so reading a saved run never needs the AI code

    question = EXAMPLES[name]
    timeline: list[dict] = []
    started = time.monotonic()

    def note(message: str) -> None:
        timeline.append({"at": round(time.monotonic() - started, 1), "message": message})
        if on_progress:
            on_progress(message)

    time_limit = config.RUN_TIME_LIMIT_SECONDS if config.DEMO_MODE else None
    state = run_research(question, on_progress=note, time_limit=time_limit)
    return {
        "name": name,
        "question": question,
        "report": state["report"],
        "sources": state.get("sources", []),
        "subtasks": state.get("subtasks", []),
        "progress": [step["message"] for step in timeline],
        "timeline": timeline,
        "took_seconds": round(time.monotonic() - started, 1),
        "made_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settings": {
            "lead_model": config.LEAD_MODEL,
            "worker_model": config.WORKER_MODEL,
            "max_subtasks": config.MAX_SUBTASKS,
            "max_searches_per_researcher": config.MAX_SEARCHES_PER_RESEARCHER,
            "max_revisions": config.MAX_REVISIONS,
        },
    }
