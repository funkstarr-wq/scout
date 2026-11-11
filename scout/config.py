"""Settings for Scout. Values come from the .env file or the environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# The lead model plans, writes and reviews. The worker model does the searching.
LEAD_MODEL = os.getenv("SCOUT_LEAD_MODEL", "claude-sonnet-5-5")
WORKER_MODEL = os.getenv("SCOUT_WORKER_MODEL", "claude-haiku-5-5")

# Effort limits. These keep a single question from running up a large bill.
MAX_SUBTASKS = 5          # most researchers the planner may start
MAX_RESEARCH_TURNS = 8    # most back-and-forth turns for one researcher
MAX_SEARCHES_PER_RESEARCHER = 5
MAX_FINDINGS_PER_RESEARCHER = 8
MAX_REVISIONS = 1         # how many times the writer may redo a rejected report

DB_PATH = os.getenv("SCOUT_DB", str(PROJECT_ROOT / "scout.db"))
PASSWORD = os.getenv("SCOUT_PASSWORD", "")
DAILY_LIMIT = int(os.getenv("SCOUT_DAILY_LIMIT", "25"))
