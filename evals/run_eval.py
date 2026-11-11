"""Scout's exam. Runs a set of questions and has Claude grade every report.

    python -m evals.run_eval            # all questions
    python -m evals.run_eval --limit 3  # just the first three (cheaper)

Prints a line like "SCORE: 0.812" and appends one row to evals/results.tsv.
This file and questions.jsonl are the referee: agents must never edit them.
"""
import argparse
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scout import config
from scout.agents import ask_for_tool, format_findings, number_sources
from scout.graph import run_research

HERE = Path(__file__).resolve().parent

GRADE_TOOL = {
    "name": "submit_grade",
    "description": "Submit scores for the research report.",
    "input_schema": {
        "type": "object",
        "properties": {
            "factual_accuracy": {"type": "number", "description": "0.0-1.0: do the report's claims match the findings?"},
            "citation_accuracy": {"type": "number", "description": "0.0-1.0: does each citation support its sentence?"},
            "completeness": {"type": "number", "description": "0.0-1.0: are all must_cover points answered?"},
            "source_quality": {"type": "number", "description": "0.0-1.0: primary, reputable sources rather than content farms?"},
            "clarity": {"type": "number", "description": "0.0-1.0: does it lead with the answer and read clearly?"},
            "comment": {"type": "string", "description": "One sentence on the biggest weakness."},
        },
        "required": ["factual_accuracy", "citation_accuracy", "completeness", "source_quality", "clarity", "comment"],
    },
}

JUDGE_PROMPT = """You are a strict but fair examiner grading a research report written by an AI research assistant.
You will see the question, the points a good answer must cover, the findings the researchers collected
(with their sources), and the final report. Grade each criterion from 0.0 to 1.0. Judge citation and
factual accuracy only against the findings. Call submit_grade."""


def grade(item: dict, state: dict) -> dict:
    number_sources(state["findings"])
    sources = "\n".join(f"[{s['n']}] {s['title']} - {s['url']}" for s in state.get("sources", []))
    scores = ask_for_tool(config.LEAD_MODEL, JUDGE_PROMPT, GRADE_TOOL, (
        f"<question>{item['question']}</question>\n"
        f"<must_cover>{json.dumps(item['must_cover'])}</must_cover>\n"
        f"{format_findings(state['findings'])}\n<sources>\n{sources}\n</sources>\n"
        f"<report>\n{state['report']}\n</report>"))
    keys = ["factual_accuracy", "citation_accuracy", "completeness", "source_quality", "clarity"]
    scores["overall"] = round(sum(float(scores[k]) for k in keys) / len(keys), 3)
    return scores


def run_one(item: dict) -> dict:
    started = time.time()
    try:
        state = run_research(item["question"])
        scores = grade(item, state)
    except Exception as exc:
        scores = {"overall": 0.0, "comment": f"crashed: {exc}"}
    scores["seconds"] = round(time.time() - started)
    scores["question"] = item["question"]
    return scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only run the first N questions")
    args = parser.parse_args()

    items = [json.loads(line) for line in (HERE / "questions.jsonl").read_text().splitlines() if line.strip()]
    items = items[: args.limit] if args.limit else items

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run_one, items))

    for r in results:
        print(f"{r['overall']:.2f}  {r['seconds']:>4}s  {r['question'][:70]}  -- {r.get('comment', '')}")
    score = round(sum(r["overall"] for r in results) / len(results), 3)
    print(f"\nSCORE: {score}")

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ""
    log = HERE / "results.tsv"
    if not log.exists():
        log.write_text("time\tcommit\tquestions\tscore\n")
    with log.open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')}\t{commit or '-'}\t{len(results)}\t{score}\n")


if __name__ == "__main__":
    main()
