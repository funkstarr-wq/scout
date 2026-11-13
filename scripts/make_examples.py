"""Make the three example reports for the website.

THIS CALLS THE REAL CLAUDE API AND COSTS MONEY: roughly 10 US cents per report,
so about 30 cents for all three. It asks before it spends anything.

Run it from the project folder, with the virtual environment active:

    python scripts/make_examples.py                    # all three
    python scripts/make_examples.py coffee-and-sleep   # just one

Each report is saved to scout/static/examples/<name>.json, with its progress
log, and the website shows it at /examples/<name>. Commit those files.
Running it again overwrites them.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

if __name__ == "__main__":
    # Use the live demo's cheaper settings, so the examples look like what visitors get.
    # This has to happen before Scout's settings are loaded below.
    os.environ["DEMO_MODE"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # make "import scout" work from any folder

from scout import config, examples  # noqa: E402
from scout.graph import run_research  # noqa: E402

CENTS_PER_REPORT = 10  # a rough estimate with the demo settings; /admin/spend and the Console show real figures


def make_one(name: str, out_dir: Path) -> Path:
    """Research one example question and save the result. Returns the file it wrote."""
    question = examples.EXAMPLES[name]
    progress: list[str] = []

    def note(message: str) -> None:
        progress.append(message)
        print(f"   {message}")

    state = run_research(question, on_progress=note)
    example = {
        "name": name,
        "question": question,
        "report": state["report"],
        "sources": state.get("sources", []),
        "subtasks": state.get("subtasks", []),
        "progress": progress,
        "made_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settings": {
            "lead_model": config.LEAD_MODEL,
            "worker_model": config.WORKER_MODEL,
            "max_subtasks": config.MAX_SUBTASKS,
            "max_searches_per_researcher": config.MAX_SEARCHES_PER_RESEARCHER,
            "max_revisions": config.MAX_REVISIONS,
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(example, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)  # only swap in the new file once it is complete
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make the example reports for the website (costs money).")
    parser.add_argument("names", nargs="*", help=f"which examples to make: {', '.join(examples.EXAMPLES)} (default: all)")
    parser.add_argument("--yes", action="store_true", help="don't ask 'are you sure?' first")
    args = parser.parse_args(argv)

    names = args.names or list(examples.EXAMPLES)
    unknown = [n for n in names if n not in examples.EXAMPLES]
    if unknown:
        print(f"Unknown example(s): {', '.join(unknown)}. Choose from: {', '.join(examples.EXAMPLES)}")
        return 2
    if config.FAKE_MODE:
        print("SCOUT_FAKE is on, so these would be made-up reports. Turn it off and run this again.")
        return 2

    print(f"This researches {len(names)} question(s) with the real Claude API, using the live demo's settings:")
    rewrites = "no rewrite" if config.MAX_REVISIONS == 0 else f"up to {config.MAX_REVISIONS} rewrite(s)"
    print(f"up to {config.MAX_SUBTASKS} researchers, {config.MAX_SEARCHES_PER_RESEARCHER} searches each, {rewrites}, "
          f"using {config.LEAD_MODEL} and {config.WORKER_MODEL}.")
    print(f"It will cost roughly {len(names) * CENTS_PER_REPORT} US cents and take a few minutes.")
    if not args.yes and input("Type yes to go ahead: ").strip().lower() != "yes":
        print("Stopped. Nothing was spent.")
        return 1

    for name in names:
        print(f"\n{examples.EXAMPLES[name]}")
        path = make_one(name, examples.EXAMPLES_DIR)
        print(f"   Saved {path.relative_to(ROOT)}")
    print("\nDone. Commit the files in scout/static/examples/ so the website can show them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
