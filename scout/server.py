"""Scout's web server. Start it with:  uvicorn scout.server:app --reload

Pages:
    /                  the book's website (always public)
    /book              the free-book form posts here; download links are /book/<token>/pdf or /epub
    /admin/signups.csv the list of readers who asked for the book (needs SCOUT_ADMIN_PASSWORD)
    /demo              the Scout page itself (password-protected unless DEMO_MODE is on)
    /examples/<name>   three finished example reports (always public, never call Claude)
    /privacy           what the live demo stores (always public)
"""
import csv
import hashlib
import hmac
import html
import io
import ipaddress
import logging
import re
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from . import config, examples, store
from .graph import run_research

# Refuse to start, with a clear message, if the live demo is missing a safety setting.
config.check_settings()

STATIC = Path(__file__).resolve().parent / "static"
SITE = STATIC / "site"
VISITOR_COOKIE = "scout_visitor"
log = logging.getLogger("scout")


def tidy_demo_data() -> None:
    """Delete demo questions after KEEP_DEMO_DAYS, and visitor fingerprints after their day."""
    store.delete_old_jobs(config.KEEP_DEMO_DAYS)
    store.forget_old_fingerprints()


@asynccontextmanager
async def lifespan(_app):
    if config.DEMO_MODE:
        tidy_demo_data()
        store.fail_unfinished_jobs("Scout restarted before this question finished. Please try again.")
    yield


app = FastAPI(title="Scout", lifespan=lifespan)
basic = HTTPBasic(auto_error=False)


def require_password(credentials: HTTPBasicCredentials | None = Depends(basic)):
    """If SCOUT_PASSWORD is set, ask the browser for it (username: scout).

    The live demo (DEMO_MODE) is public, so it never asks.
    """
    if config.DEMO_MODE or not config.PASSWORD:
        return
    ok = credentials is not None and secrets.compare_digest(
        credentials.username.encode() + b":" + credentials.password.encode(),
        b"scout:" + config.PASSWORD.encode(),
    )
    if not ok:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})


class Question(BaseModel):
    question: str = Field(max_length=5000)  # refuse absurdly long requests before doing anything


# ------------------------------------------------------------ live demo helpers
class RunSlots:
    """Counts how many demo questions are running, so only MAX_CONCURRENT run at once."""

    def __init__(self):
        self.running = 0
        self._lock = threading.Lock()

    def try_take(self) -> bool:
        with self._lock:
            if self.running >= config.MAX_CONCURRENT:
                return False
            self.running += 1
            return True

    def give_back(self) -> None:
        with self._lock:
            self.running = max(0, self.running - 1)


slots = RunSlots()


def visitor_ip(request: Request) -> str:
    """The visitor's internet address.

    On Railway every request arrives through Railway's own proxy, which passes
    the visitor's real address in the X-Real-IP header. Only the live demo
    trusts that header; anywhere else it could be faked.
    """
    if config.DEMO_MODE:
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
    return request.client.host if request.client else "unknown"


def visitor_network(ip: str) -> str:
    """The part of an address that identifies one household or phone.

    A home on IPv6 gets a whole block of addresses (a /64) and can hop between
    them, so the whole block counts as one visitor.
    """
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if address.version == 6:
        if address.ipv4_mapped is not None:  # an IPv4 address written the IPv6 way
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def ip_fingerprint(ip: str, day: str) -> str:
    """A one-way code made from the address, today's date and a secret salt.

    It can tell whether two questions came from the same address on the same
    day. Only someone with the salt could work out which address made it, and
    because the date is mixed in, one day's codes can't be matched with the
    next day's. Fingerprints are wiped once their day is over, and the address
    itself is never stored or logged.
    """
    return hmac.new(config.IP_SALT.encode(), f"{ip}|{day}".encode(), hashlib.sha256).hexdigest()


def cookie_visitor_id(request: Request) -> str | None:
    """The visitor's ID from their cookie, if they have a valid one."""
    vid = request.cookies.get(VISITOR_COOKIE, "")
    return vid if re.fullmatch(r"[A-Za-z0-9_-]{16,64}", vid) else None


def visitor_id(request: Request, response: Response) -> str:
    """A random ID kept in a cookie, so each visitor sees only their own questions."""
    vid = cookie_visitor_id(request) or secrets.token_urlsafe(18)
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        VISITOR_COOKIE, vid, max_age=config.KEEP_DEMO_DAYS * 86400,
        httponly=True, samesite="lax", secure=https, path="/",
    )
    return vid


def max_question_chars() -> int:
    return config.DEMO_QUESTION_MAX_CHARS if config.DEMO_MODE else config.QUESTION_MAX_CHARS


REFUSALS = {
    "visitor": (429, "You've used your {n} questions for today. Come back tomorrow, or have a look at the example reports."),
    "daily": (429, "The demo has answered all the questions it can afford today. It resets overnight. "
                   "Meanwhile, here are three finished reports."),
    "busy": (503, "Scout is busy with someone else's question. Please try again in a minute."),
}
NO_COOKIE = ("Scout needs a cookie to show you your report. Please allow cookies for this site, "
             "reload the page and try again.")


def refusal(reason: str) -> HTTPException:
    if not config.DEMO_MODE:  # your own copy keeps its original wording
        return HTTPException(429, "Scout has reached today's question limit. Try again tomorrow.")
    status, message = REFUSALS[reason]
    headers = {"Retry-After": "60"} if reason == "busy" else None
    return HTTPException(status, message.format(n=config.PER_VISITOR_LIMIT), headers=headers)


def public(job: dict) -> dict:
    """A job as the page sees it, without the private columns."""
    return {k: v for k, v in job.items() if k not in ("visitor_id", "ip_hash")}


# -------------------------------------------------------------------- the work
def run_job(job_id: str, question: str, holds_slot: bool = False) -> None:
    time_limit = config.RUN_TIME_LIMIT_SECONDS if config.DEMO_MODE else None
    try:
        state = run_research(
            question, on_progress=lambda msg: store.add_progress(job_id, msg), time_limit=time_limit
        )
        store.finish_job(job_id, state["report"])
    except TimeoutError:
        store.fail_job(job_id, "Scout ran out of time on this question, so it stopped to keep costs down. "
                               "A narrower question usually works better.")
    except Exception as exc:  # show the error on the page rather than failing silently
        log.exception("Research job %s failed", job_id)
        if config.DEMO_MODE:  # strangers don't need to see the details of an API error
            store.fail_job(job_id, "Something went wrong while Scout was researching this. Please try again later.")
        else:
            store.fail_job(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        if holds_slot:
            slots.give_back()


# ----------------------------------------------------------------------- pages
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def home():
    return FileResponse(SITE / "index.html")


@app.get("/cover.jpg")
def cover():
    return FileResponse(SITE / "cover.jpg")


@app.get("/og-image.jpg")
def og_image():
    return FileResponse(SITE / "og-image.jpg")


@app.get("/author.jpg")
def author_photo():
    return FileResponse(SITE / "author.jpg")


@app.get("/demo", dependencies=[Depends(require_password)])
def demo(request: Request):
    page = FileResponse(STATIC / "index.html")
    if config.DEMO_MODE:
        visitor_id(request, page)
    return page


@app.get("/examples/{name}")
def example_page(name: str):
    if name not in examples.EXAMPLES:
        return FileResponse(STATIC / "not_found.html", status_code=404)
    if examples.load(name) is None:
        return FileResponse(STATIC / "coming_soon.html")
    return FileResponse(STATIC / "example.html")


@app.get("/privacy")
def privacy():
    return FileResponse(STATIC / "privacy.html")


# --------------------------------------------------------------- the free book
FONT_FILE = re.compile(r"charis-sil-latin-(400|700)-(normal|italic)\.woff2")
EDITIONS = {"pdf": ("Building-Scout.pdf", "application/pdf"), "epub": ("Building-Scout.epub", "application/epub+zip")}
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
LONGEST_FORM = 10_000  # bytes; the real form is a few hundred


def fill_page(template: str, status_code: int = 200, **values: str) -> HTMLResponse:
    """A page from scout/static with its {{PLACEHOLDERS}} filled in. Values are escaped, so a
    name typed into the form shows as text and can never add anything to the page."""
    text = (STATIC / template).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", html.escape(value))
    return HTMLResponse(text, status_code=status_code)


def book_problem(title: str, message: str, status_code: int) -> HTMLResponse:
    return fill_page("book_problem.html", status_code, TITLE=title, MESSAGE=message)


def spreadsheet_safe(value: str) -> str:
    """Stop a 'name' like =HYPERLINK(...) from running as a formula when the list is opened in Excel."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@app.get("/fonts/{name}")
def font(name: str):
    if not FONT_FILE.fullmatch(name):
        raise HTTPException(404, "No such font.")
    return FileResponse(STATIC / "fonts" / name, media_type="font/woff2",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/book")
def book_form():
    return RedirectResponse("/#free", status_code=303)


@app.post("/book")
async def ask_for_book(request: Request):
    if int(request.headers.get("content-length") or 0) > LONGEST_FORM:
        return book_problem("That was more than the form expects", "Please go back and try again.", 413)
    body = await request.body()
    if len(body) > LONGEST_FORM:
        return book_problem("That was more than the form expects", "Please go back and try again.", 413)
    form = {key: values[0] for key, values in parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True).items()}
    first_name = " ".join(form.get("first_name", "").split())
    surname = " ".join(form.get("surname", "").split())
    email = form.get("email", "").strip()

    if form.get("website"):  # a hidden box people never see; only robots fill it in
        return book_problem("Something went wrong", "Please go back and try again.", 400)
    if not (1 <= len(first_name) <= 60 and 1 <= len(surname) <= 60):
        return book_problem("Please add your name", "The book needs your first name and surname. Go back and fill them in.", 400)
    if len(email) > 254 or not EMAIL.fullmatch(email):
        return book_problem("Please check your email address",
                            f"\u201c{email}\u201d doesn't look like an email address. Go back and check it.", 400)

    token = store.save_signup(first_name, surname, email, email_ok=form.get("email_ok") == "yes")
    return fill_page("book_ready.html", FIRST_NAME=first_name,
                     PDF_URL=f"/book/{token}/pdf", EPUB_URL=f"/book/{token}/epub")


@app.get("/book/{token}/{edition}")
def download_book(token: str, edition: str):
    signup = store.find_signup(token) if edition in EDITIONS else None
    if signup is None:
        return book_problem("This download link doesn't work",
                            "It may have been replaced by a newer one. Fill in the form again for a fresh link.", 404)
    made = datetime.fromisoformat(signup["token_created_at"])
    if store.utcnow() - made > timedelta(days=config.BOOK_LINK_DAYS):
        return book_problem("This download link has expired",
                            f"Links work for {config.BOOK_LINK_DAYS} days. Fill in the form again for a new one.", 410)
    filename, media_type = EDITIONS[edition]
    path = config.BOOK_DIR / filename
    if not path.exists():
        return book_problem("The book isn't quite ready", "Please try again a little later.", 503)
    store.count_download(token)
    return FileResponse(path, media_type=media_type, filename=filename, headers={"Cache-Control": "private, no-store"})


@app.get("/admin/signups.csv")
def signups_csv(credentials: HTTPBasicCredentials | None = Depends(basic)):
    """The readers who asked for the book, as a spreadsheet. Username: admin."""
    if not config.ADMIN_PASSWORD:
        raise HTTPException(404)
    ok = credentials is not None and secrets.compare_digest(
        credentials.username.encode() + b":" + credentials.password.encode(),
        b"admin:" + config.ADMIN_PASSWORD.encode(),
    )
    if not ok:
        raise HTTPException(401, headers={"WWW-Authenticate": 'Basic realm="Building Scout admin"'})
    out = io.StringIO()
    sheet = csv.writer(out)
    sheet.writerow(["First name", "Surname", "Email", "Happy to get emails", "First asked", "Last asked", "Downloads"])
    for row in store.list_signups():
        sheet.writerow([spreadsheet_safe(row["first_name"]), spreadsheet_safe(row["surname"]),
                        spreadsheet_safe(row["email"]), "yes" if row["email_ok"] else "no",
                        row["created_at"], row["updated_at"], row["downloads"]])
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="building-scout-readers.csv"',
                             "Cache-Control": "no-store"})


# ------------------------------------------------------------------------- API
@app.get("/api/settings")
def settings():
    """What the Scout page needs to know about how this copy is set up."""
    return {
        "demo": config.DEMO_MODE,
        "fake": config.FAKE_MODE,
        "max_chars": max_question_chars(),
        "per_visitor": config.PER_VISITOR_LIMIT,
        "examples": [{"name": n, "question": q} for n, q in examples.EXAMPLES.items()],
    }


@app.get("/api/examples/{name}")
def example_data(name: str):
    data = examples.load(name)
    if data is None:
        raise HTTPException(404, "No such example report.")
    return data


@app.post("/api/research", dependencies=[Depends(require_password)])
def start_research(body: Question, background: BackgroundTasks, request: Request):
    question = body.question.strip()
    longest = max_question_chars()
    if not config.QUESTION_MIN_CHARS <= len(question) <= longest:
        raise HTTPException(400, f"Please write a question between {config.QUESTION_MIN_CHARS} and {longest} characters long.")

    if not config.DEMO_MODE:
        job_id, reason = store.try_create_job(question, config.DAILY_LIMIT)
        if job_id is None:
            raise refusal(reason)
        background.add_task(run_job, job_id, question)
        return {"id": job_id}

    # The page gets its cookie when it loads. Without one, the visitor could never see their
    # report, so refuse before the question counts or costs anything.
    vid = cookie_visitor_id(request)
    if vid is None:
        raise HTTPException(400, NO_COOKIE)
    tidy_demo_data()
    got_slot = slots.try_take()
    try:
        job_id, reason = store.try_create_job(
            question,
            config.DAILY_LIMIT,
            visitor_id=vid,
            ip_hash=ip_fingerprint(visitor_network(visitor_ip(request)), store.today()),
            per_visitor_limit=config.PER_VISITOR_LIMIT,
            can_start=got_slot,
        )
    except BaseException:
        if got_slot:
            slots.give_back()
        raise
    if job_id is None:
        if got_slot:
            slots.give_back()
        raise refusal(reason)
    background.add_task(run_job, job_id, question, holds_slot=True)
    return {"id": job_id}


@app.get("/api/research/{job_id}", dependencies=[Depends(require_password)])
def get_research(job_id: str, request: Request):
    job = store.get_job(job_id)
    if job is None or (config.DEMO_MODE and (job["visitor_id"] is None
                                             or job["visitor_id"] != cookie_visitor_id(request))):
        raise HTTPException(404, "No such research job.")
    return public(job)


@app.get("/api/history", dependencies=[Depends(require_password)])
def history(request: Request):
    if config.DEMO_MODE:
        mine = cookie_visitor_id(request)
        return store.list_jobs(visitor_id=mine) if mine else []
    return store.list_jobs()
