"""Saves research jobs and their reports in a small SQLite database file."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone

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
               created_at TEXT NOT NULL
           )"""
    )
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_job(question: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _connect() as conn:
        conn.execute(
            "INSERT INTO jobs (id, question, status, created_at) VALUES (?, ?, 'running', ?)",
            (job_id, question, _now()),
        )
    return job_id


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


def list_jobs(limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, question, status, created_at FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def count_jobs_today() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM jobs WHERE created_at >= ?", (today,)).fetchone()
    return row["n"]
