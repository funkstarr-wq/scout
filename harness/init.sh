#!/usr/bin/env bash
# Gets a fresh session ready to work: installs packages and proves the tests pass.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
pip install -q -r requirements.txt
python -m pytest -q
echo "Ready. Start the app with: uvicorn scout.server:app --reload"
