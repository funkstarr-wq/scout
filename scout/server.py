"""Scout's web server. Start it with:  uvicorn scout.server:app --reload"""
import secrets
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from . import config, store
from .graph import run_research

app = FastAPI(title="Scout")
STATIC = Path(__file__).resolve().parent / "static"
basic = HTTPBasic(auto_error=False)


def require_password(credentials: HTTPBasicCredentials | None = Depends(basic)):
    """If SCOUT_PASSWORD is set, ask the browser for it (username: scout)."""
    if not config.PASSWORD:
        return
    ok = credentials is not None and secrets.compare_digest(
        credentials.username.encode() + b":" + credentials.password.encode(),
        b"scout:" + config.PASSWORD.encode(),
    )
    if not ok:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})


class Question(BaseModel):
    question: str


def run_job(job_id: str, question: str) -> None:
    try:
        state = run_research(question, on_progress=lambda msg: store.add_progress(job_id, msg))
        store.finish_job(job_id, state["report"])
    except Exception as exc:  # show the error on the page rather than failing silently
        store.fail_job(job_id, f"{type(exc).__name__}: {exc}")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", dependencies=[Depends(require_password)])
def home():
    return FileResponse(STATIC / "index.html")


@app.post("/api/research", dependencies=[Depends(require_password)])
def start_research(body: Question, background: BackgroundTasks):
    question = body.question.strip()
    if not 10 <= len(question) <= 500:
        raise HTTPException(400, "Please write a question between 10 and 500 characters long.")
    if store.count_jobs_today() >= config.DAILY_LIMIT:
        raise HTTPException(429, "Scout has reached today's question limit. Try again tomorrow.")
    job_id = store.create_job(question)
    background.add_task(run_job, job_id, question)
    return {"id": job_id}


@app.get("/api/research/{job_id}", dependencies=[Depends(require_password)])
def get_research(job_id: str):
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(404, "No such research job.")
    return job


@app.get("/api/history", dependencies=[Depends(require_password)])
def history():
    return store.list_jobs()
