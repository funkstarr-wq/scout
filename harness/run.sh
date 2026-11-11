#!/usr/bin/env bash
# Runs up to N shifts of Claude Code, one feature per shift.  Usage: bash harness/run.sh 3
cd "$(dirname "$0")/.."
SHIFTS=${1:-1}
for i in $(seq 1 "$SHIFTS"); do
  if ! grep -q '"passes": false' harness/feature_list.json; then
    echo "Every feature passes. Nothing left to do."; break
  fi
  echo "=== Shift $i of $SHIFTS ==="
  claude -p "$(cat harness/coding_prompt.md)" \
    --permission-mode acceptEdits \
    --allowedTools "Bash(python *)" "Bash(bash harness/init.sh)" "Bash(git *)" "Bash(pwd)" "Bash(uvicorn *)"
done
