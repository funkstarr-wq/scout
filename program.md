# Scout autoresearch

You are improving Scout's prompts by experiment, the way Karpathy's autoresearch improves a training
script. The human may be away. Work through the loop below without asking whether to continue,
until you have run the number of experiments you were given (default: 5). Then stop and report.

## What you may change
- ONLY the files in `scout/prompts/` (planner.md, researcher.md, writer.md, reviewer.md).
- Nothing else. Not the code, not the tests, and never anything in `evals/`.

## Setup (once)
1. Make sure the working tree is clean (`git status`). Create a branch: `git checkout -b autoresearch/<today's date>`.
2. Run the baseline: `python -m evals.run_eval --limit 4`. Note the SCORE. That is the score to beat.

## The loop (one experiment)
1. Read the latest results in `evals/results.tsv` and the grader's comments from the last run.
   Form ONE hypothesis about a prompt change that would raise the score. Write it down in one sentence.
2. Make that single change to one prompt file. Keep it small.
3. Run `python -m pytest -q` (must pass), then `python -m evals.run_eval --limit 4`.
4. If SCORE is higher than the best so far: `git commit -am "experiment: <hypothesis> (score X)"`.
   This is the new best.
5. If SCORE is the same or lower: `git checkout -- scout/prompts/` to throw the change away.
6. Append one line to `evals/experiments.md`: the hypothesis, the score, kept or discarded.

## Taste
- A prompt that gets shorter and scores the same is an improvement. Keep it.
- A tiny gain that makes a prompt much longer or more convoluted is not worth keeping.
- Scores move a little between runs by chance. Treat a change of less than 0.02 as no change.

## When you finish
Report the starting score, the best score, and the list of kept changes, in plain English.
