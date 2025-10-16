#!/bin/bash
# Simple one-command startup for Chess GPT

echo "🚀 Starting Chess GPT..."
(cd backend && python3 main.py) & (cd frontend && export PATH=/Users/hugobosnic/Desktop/chess-gpt/backend/node-v20.11.0-darwin-arm64/bin:$PATH && /Users/hugobosnic/Desktop/chess-gpt/backend/node-v20.11.0-darwin-arm64/bin/npm run dev) & wait
