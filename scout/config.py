"""Settings for Scout. Values come from the .env file or the environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _switch(name: str) -> bool:
    """Read an on/off setting like DEMO_MODE. A typo stops Scout starting rather than quietly meaning 'off'."""
    raw = os.getenv(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("", "0", "false", "no", "off"):
        return False
    raise RuntimeError(f"{name} must be 1 (on) or 0 (off). It is set to {raw!r}.")


def _dollars(name: str, default: float) -> float:
    """Read an amount of money in US dollars, like 10 or 12.50. A typo stops Scout starting."""
    raw = os.getenv(name, "").strip().lstrip("$")
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be an amount in US dollars, like 10. It is set to {raw!r}.") from None
    if value < 0:
        raise RuntimeError(f"{name} can't be negative. It is set to {value}.")
    return value


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
# The live demo uses the cheaper Haiku for both, because every question costs the owner money:
# per word, Haiku costs about a twentieth of Sonnet.
# A blank setting counts as "not set", so an empty Railway variable can't leave Scout without a model.
LEAD_MODEL = os.getenv("SCOUT_LEAD_MODEL") or ("claude-haiku-5-5" if DEMO_MODE else "claude-sonnet-5-5")
WORKER_MODEL = os.getenv("SCOUT_WORKER_MODEL") or "claude-haiku-5-5"

# Effort limits. These keep a single question from running up a large bill.
# The live demo uses smaller ones. Web searches are its biggest cost ($0.01 each), and every
# extra researcher turn means re-reading the search results gathered so far.
MAX_SUBTASKS = 3 if DEMO_MODE else 5          # most researchers the planner may start
MAX_RESEARCH_TURNS = 4 if DEMO_MODE else 8     # most back-and-forth turns for one researcher
MAX_SEARCHES_PER_RESEARCHER = 2 if DEMO_MODE else 5
MAX_FINDINGS_PER_RESEARCHER = 8
MAX_REVISIONS = 0 if DEMO_MODE else 1          # how many times the writer may redo a rejected report
WRITER_MAX_TOKENS = 3000 if DEMO_MODE else 6000  # longest report the writer may produce

DB_PATH = os.getenv("SCOUT_DB", str(PROJECT_ROOT / "scout.db"))
DB_PATH_IS_SET = bool(os.getenv("SCOUT_DB", "").strip())
PASSWORD = os.getenv("SCOUT_PASSWORD", "")
DAILY_LIMIT = _whole_number("SCOUT_DAILY_LIMIT", 25)   # questions per day, for everyone together

# Questions must be between these lengths (in characters).
QUESTION_MIN_CHARS = 10
QUESTION_MAX_CHARS = 500
DEMO_QUESTION_MAX_CHARS = 300

# Live demo limits.
PER_VISITOR_LIMIT = _whole_number("SCOUT_PER_VISITOR_LIMIT", 2)    # questions per visitor per day
MAX_CONCURRENT = _whole_number("SCOUT_MAX_CONCURRENT", 1, smallest=1)  # questions running at once
RUN_TIME_LIMIT_SECONDS = 180      # researchers stop at half of this; the fact-check is skipped after it
API_TIMEOUT_SECONDS = 120         # longest the demo waits for any single reply from Claude
API_MAX_RETRIES = 1               # the demo tries a failed reply once more at most (each try is billed)
KEEP_DEMO_DAYS = 30               # demo questions and reports are deleted after this many days
IP_SALT = os.getenv("SCOUT_IP_SALT", "")  # secret mixed into visitor fingerprints
# The most the demo may spend on the Claude API in a calendar month (UTC), in US dollars.
# Scout adds up what each reply actually costs (see spend.py) and stops taking questions
# before this is reached. Set the same limit in the Claude Console as the hard stop.
MONTHLY_BUDGET_USD = _dollars("SCOUT_MONTHLY_BUDGET_USD", 10.0)
QUESTION_RESERVE_USD = 0.50       # headroom for one more question: the demo stops this far below the budget

# The free book. Readers fill in a short form, then get download links that work for a week.
BOOK_DIR = PROJECT_ROOT / "book"          # Building-Scout.pdf and Building-Scout.epub live here
BOOK_LINK_DAYS = 7
# Password for downloading the list of readers who asked for the book (/admin/signups.csv,
# username "admin"). Leave it unset and that page doesn't exist.
ADMIN_PASSWORD = os.getenv("SCOUT_ADMIN_PASSWORD", "")


def check_settings() -> None:
    """Stop Scout from starting if the live demo would run without its safety settings."""
    if DEMO_MODE and len(IP_SALT) < 16:
        raise RuntimeError(
            "DEMO_MODE is on, but SCOUT_IP_SALT is missing or shorter than 16 characters. "
            "Set it to a long random string (see the README) and start Scout again."
        )
    if DEMO_MODE and not FAKE_MODE and not DB_PATH_IS_SET:
        raise RuntimeError(
            "DEMO_MODE is on, but SCOUT_DB isn't set. Point it at a file on a Railway volume, "
            "like /data/scout.db, or the daily limits would start again every time Scout restarts."
        )
