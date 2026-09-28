#!/usr/bin/env bash
# macOS / Linux
set -e
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
echo "Open http://localhost:8000  (staff login: ee_vadodara / Exec@123)"
python -m uvicorn app.main:app --port 8000
