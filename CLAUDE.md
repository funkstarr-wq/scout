# Scout

Scout is a research assistant web app. A user asks a question; a planner agent splits it into tasks,
parallel researcher agents search the web and record findings, a writer turns findings into a cited
Markdown report, and a reviewer checks it. Built with Python, FastAPI, LangGraph and the Claude API.

## Commands
- Set up: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run the app: `uvicorn scout.server:app --reload` then open http://127.0.0.1:8000 (website) and /demo (Scout)
- Try the live demo for free: `DEMO_MODE=1 SCOUT_FAKE=1 SCOUT_IP_SALT=practice-salt-for-my-computer uvicorn scout.server:app --reload`
- Run tests (free, no API calls): `python -m pytest -q`
- Run the evaluation (costs money, calls Claude): `python -m evals.run_eval --limit 3`
- Make the saved questions (costs money, calls Claude): `python scripts/make_examples.py`, or the button on the live site's `/admin/recordings`
- Rebuild the free book (free): `python scripts/build_book.py [new-manuscript.doc]` (needs LibreOffice and `requirements-book.txt`)

## Layout
- `scout/graph.py` the LangGraph workflow: plan -> research (parallel) -> write -> review
- `scout/agents.py` the four agents; `scout/tools.py` tool definitions and handlers
- `scout/prompts/*.md` every prompt Scout uses, as plain text
- `scout/server.py` web server: the website at `/`, Scout at `/demo`, example reports, privacy note, live demo limits
- `scout/static/index.html` the Scout page (served at /demo); `scout/static/site/` the book's website
- `scout/static/example.html`, `privacy.html`, `coming_soon.html`, `not_found.html`, `admin_recordings.html` the other pages
- `scout/examples.py` the saved questions: real runs, recorded once, that the demo replays for free and the website shows as example reports; record them at `/admin/recordings` (costs money) or with `scripts/make_examples.py`
- `book/` the free book: the PDF and EPUB readers download, plus the EPUB filter and styles; `Building-Scout.docx` is the manuscript
- `scout/static/book_ready.html`, `book_problem.html` the pages after the free-book form; sign-ups are in `store.py`
- `scout/static/fonts/` Outfit, the cover's typeface (SIL Open Font Licence); every page uses it
- `scout/store.py` SQLite storage; `scout/mcp_server.py` Scout as an MCP tool
- `scout/spend.py` prices every Claude reply so the demo stops at `SCOUT_MONTHLY_BUDGET_USD`; `/admin/spend` shows the month's total
- `tests/` uses a fake Claude (`scout/fake_llm.py`), so tests never need an API key; `SCOUT_FAKE=1` uses it in the app
- `scout/config.py` `DEMO_MODE=1` turns on the public live demo: no password, lower effort, per-visitor and daily limits; visitors only watch saved questions unless `SCOUT_LIVE_QUESTIONS=1`
- `evals/` the exam: questions plus an AI grader

## Rules
- Never read, print or edit `.env`. It holds the API key.
- Never edit `evals/questions.jsonl` or `evals/run_eval.py`; they are the referee.
- Never run anything that calls the real API (the evaluation, `scripts/make_examples.py`) unless the owner asks.
- The live demo spends the owner's money: never weaken a demo limit without asking.
- Readers' names and emails (the `signups` table) are personal data: never print, log or export them except through `/admin/signups.csv`.
- Every new feature needs a test in `tests/` that uses the fake client, not the real API.
- Keep prompts in `scout/prompts/`, not inside Python code.
- Explain changes in plain English: the owner of this project is not a programmer.
