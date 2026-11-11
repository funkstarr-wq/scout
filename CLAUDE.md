# Scout

Scout is a research assistant web app. A user asks a question; a planner agent splits it into tasks,
parallel researcher agents search the web and record findings, a writer turns findings into a cited
Markdown report, and a reviewer checks it. Built with Python, FastAPI, LangGraph and the Claude API.

## Commands
- Set up: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run the app: `uvicorn scout.server:app --reload` then open http://127.0.0.1:8000
- Run tests (free, no API calls): `python -m pytest -q`
- Run the evaluation (costs money, calls Claude): `python -m evals.run_eval --limit 3`

## Layout
- `scout/graph.py` the LangGraph workflow: plan -> research (parallel) -> write -> review
- `scout/agents.py` the four agents; `scout/tools.py` tool definitions and handlers
- `scout/prompts/*.md` every prompt Scout uses, as plain text
- `scout/server.py` web server; `scout/static/index.html` the single web page
- `scout/store.py` SQLite storage; `scout/mcp_server.py` Scout as an MCP tool
- `tests/` uses a fake Claude (`tests/fake_llm.py`), so tests never need an API key
- `evals/` the exam: questions plus an AI grader

## Rules
- Never read, print or edit `.env`. It holds the API key.
- Never edit `evals/questions.jsonl` or `evals/run_eval.py`; they are the referee.
- Every new feature needs a test in `tests/` that uses the fake client, not the real API.
- Keep prompts in `scout/prompts/`, not inside Python code.
- Explain changes in plain English: the owner of this project is not a programmer.
