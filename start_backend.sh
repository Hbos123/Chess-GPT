#!/bin/bash
# Kill any existing backend process on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 1
# Start the backend
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
