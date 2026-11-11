"""The three example reports shown on the website.

They are made once, with scripts/make_examples.py, and saved as JSON files in
scout/static/examples/. Reading them never calls the Claude API, so they cost
nothing however many people look. The questions match the cards on the website.
"""
import json
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent / "static" / "examples"

EXAMPLES = {
    "coffee-and-sleep": "Does drinking coffee affect how well you sleep?",
    "heat-pumps-vs-gas-boilers": "How do heat pumps compare with gas boilers for a typical UK home?",
    "four-day-week-trials": "What did the UK's four-day working week trials find?",
}


def load(name: str) -> dict | None:
    """The saved example, or None if the name is unknown or the file hasn't been made yet."""
    if name not in EXAMPLES:  # only these exact names, so a name can never point elsewhere
        return None
    try:
        return json.loads((EXAMPLES_DIR / f"{name}.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None
