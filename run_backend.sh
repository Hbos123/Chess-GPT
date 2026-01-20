#!/bin/bash
cd "$(dirname "$0")/backend"
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
