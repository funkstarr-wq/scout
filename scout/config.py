"""Settings for Scout. Values come from the .env file or the environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _switch(name: str) -> bool:
    """True when a setting like DEMO_MODE is set to 1, true, yes or on."""
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def _whole_number(name: str, default: int, smallest: int = 0) -> int:
    """Read a whole-number setting. A typo stops Scout starting rather than meaning 'no limit'."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a whole number, like {default}. It is set to {raw!r}.") from None
    if value < smallest:
        raise RuntimeError(f"{name} must be {smallest} or more. It is set to {value}.")
    return value


# The live demo: a public copy of Scout that strangers can try, paid for by the owner.
# When it is on, there is no password, effort is lower and every visitor is limited.
DEMO_MODE = _switch("DEMO_MODE")
# A pretend Claude for trying the app for free. Answers are made up; the page says so.
FAKE_MODE = _switch("SCOUT_FAKE")

# The lead model plans, writes and reviews. The worker model does the searching.
LEAD_MODEL = os.getenv("SCOUT_LEAD_MODEL", "claude-sonnet-5-5")
WORKER_MODEL = os.getenv("SCOUT_WORKER_MODEL", "claude-haiku-5-5")

# Effort limits. These keep a single question from running up a large bill.
# The live demo uses smaller ones, because every question costs the owner money.
MAX_SUBTASKS = 3 if DEMO_MODE else 5          # most researchers the planner may start
MAX_RESEARCH_TURNS = 8                         # most back-and-forth turns for one researcher
MAX_SEARCHES_PER_RESEARCHER = 3 if DEMO_MODE else 5
MAX_FINDINGS_PER_RESEARCHER = 8
MAX_REVISIONS = 0 if DEMO_MODE else 1          # how many times the writer may redo a rejected report

DB_PATH = os.getenv("SCOUT_DB", str(PROJECT_ROOT / "scout.db"))
PASSWORD = os.getenv("SCOUT_PASSWORD", "")
DAILY_LIMIT = _whole_number("SCOUT_DAILY_LIMIT", 25)   # questions per day, for everyone together

# Questions must be between these lengths (in characters).
QUESTION_MIN_CHARS = 10
QUESTION_MAX_CHARS = 500
DEMO_QUESTION_MAX_CHARS = 300

# Live demo limits.
PER_VISITOR_LIMIT = _whole_number("SCOUT_PER_VISITOR_LIMIT", 2)    # questions per visitor per day
MAX_CONCURRENT = _whole_number("SCOUT_MAX_CONCURRENT", 1, smallest=1)  # questions running at once
RUN_TIME_LIMIT_SECONDS = 180      # a demo question that takes longer than this is stopped
API_TIMEOUT_SECONDS = 120         # longest the demo waits for any single reply from Claude
KEEP_DEMO_DAYS = 30               # demo questions and reports are deleted after this many days
IP_SALT = os.getenv("SCOUT_IP_SALT", "")  # secret mixed into visitor fingerprints


def check_settings() -> None:
    """Stop Scout from starting if the live demo would run without its safety settings."""
    if DEMO_MODE and len(IP_SALT) < 16:
        raise RuntimeError(
            "DEMO_MODE is on, but SCOUT_IP_SALT is missing or shorter than 16 characters. "
            "Set it to a long random string (see the README) and start Scout again."
        )
