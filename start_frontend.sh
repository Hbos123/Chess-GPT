#!/bin/bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend

# Ensure frontend talks to the correct backend port (backend runs on 8000)
export NEXT_PUBLIC_BACKEND_URL="http://localhost:8000"

npm run dev
