#!/bin/bash
# Kill any existing backend process on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 1
# Start the backend
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
# Activate backend virtualenv so uvicorn + deps are available.
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi
# NOTE: --reload runs a single worker and can be starved by CPU-heavy background analysis.
# Use multiple workers so the API remains responsive while analysis runs.
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
