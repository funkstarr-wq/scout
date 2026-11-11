"""Saves research jobs and their reports in a small SQLite database file."""
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from . import config


def _connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS jobs (
               id TEXT PRIMARY KEY,
               question TEXT NOT NULL,
               status TEXT NOT NULL,
               progress TEXT NOT NULL DEFAULT '[]',
               report TEXT,
               error TEXT,
               created_at TEXT NOT NULL,
               visitor_id TEXT,
               ip_hash TEXT
           )"""
    )
    # Databases made before the live demo existed lack the last two columns. Add them.
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    for column in ("visitor_id", "ip_hash"):
        if column not in columns:
            try:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} TEXT")
            except sqlite3.OperationalError:
                pass  # another request added it a moment ago
    return conn


def utcnow() -> datetime:
    """The current time in UTC. Tests replace this to pretend it is another day."""
    return datetime.now(timezone.utc)


def today() -> str:
    """Today's date in UTC, like 2026-11-11. Daily limits reset when this changes."""
    return utcnow().date().isoformat()


def _now() -> str:
    return utcnow().isoformat(timespec="seconds")


def create_job(question: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _connect() as conn:
        conn.execute(
            "INSERT INTO jobs (id, question, status, created_at) VALUES (?, ?, 'running', ?)",
            (job_id, question, _now()),
        )
    return job_id


def try_create_job(
    question: str,
    daily_limit: int,
    *,
    visitor_id: str | None = None,
    ip_hash: str | None = None,
    per_visitor_limit: int | None = None,
    can_start: bool = True,
) -> tuple[str | None, str | None]:
    """Check the limits and record the question in one step.

    Doing both inside one locked transaction means two people pressing Ask at
    the same moment can't both slip under a limit. Returns (job_id, None) when
    the question is accepted, or (None, reason) when it isn't. The reason is
    "daily" (everyone's limit for today), "visitor" (this visitor's limit) or
    "busy" (the limits are fine but Scout is already working on a question).
    A refused question is not recorded, so it doesn't count against anyone.
    """
    conn = _connect()
    conn.isolation_level = None  # we start and finish the transaction ourselves
    try:
        conn.execute("BEGIN IMMEDIATE")  # lock the database for writing until COMMIT
        try:
            day = today()
            used_today = conn.execute("SELECT COUNT(*) FROM jobs WHERE created_at >= ?", (day,)).fetchone()[0]
            if used_today >= daily_limit:
                reason = "daily"
            elif per_visitor_limit is not None and conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE ip_hash = ? AND created_at >= ?", (ip_hash, day)
            ).fetchone()[0] >= per_visitor_limit:
                reason = "visitor"
            elif not can_start:
                reason = "busy"
            else:
                reason = None
                job_id = uuid.uuid4().hex[:12]
                conn.execute(
                    "INSERT INTO jobs (id, question, status, created_at, visitor_id, ip_hash) "
                    "VALUES (?, ?, 'running', ?, ?, ?)",
                    (job_id, question, _now(), visitor_id, ip_hash),
                )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return (None, reason) if reason else (job_id, None)


def add_progress(job_id: str, message: str) -> None:
    with _connect() as conn:
        row = conn.execute("SELECT progress FROM jobs WHERE id = ?", (job_id,)).fetchone()
        progress = json.loads(row["progress"]) + [message]
        conn.execute("UPDATE jobs SET progress = ? WHERE id = ?", (json.dumps(progress), job_id))


def finish_job(job_id: str, report: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE jobs SET status = 'done', report = ? WHERE id = ?", (report, job_id))


def fail_job(job_id: str, error: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE jobs SET status = 'failed', error = ? WHERE id = ?", (error, job_id))


def get_job(job_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    job = dict(row)
    job["progress"] = json.loads(job["progress"])
    return job


def list_jobs(limit: int = 20, visitor_id: str | None = None) -> list[dict]:
    """The most recent questions: everyone's, or only one visitor's if visitor_id is given."""
    query = "SELECT id, question, status, created_at FROM jobs"
    params: tuple = ()
    if visitor_id is not None:
        query += " WHERE visitor_id = ?"
        params = (visitor_id,)
    with _connect() as conn:
        rows = conn.execute(query + " ORDER BY created_at DESC LIMIT ?", params + (limit,)).fetchall()
    return [dict(r) for r in rows]


def count_jobs_today() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM jobs WHERE created_at >= ?", (today(),)).fetchone()
    return row["n"]


def delete_old_jobs(days: int) -> int:
    """Delete questions and reports older than this many days. Returns how many were deleted."""
    cutoff = (utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
    with _connect() as conn:
        deleted = conn.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff,)).rowcount
    return deleted
