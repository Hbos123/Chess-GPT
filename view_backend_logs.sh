#!/bin/bash
# View backend logs - if running in background, shows how to see them

echo "Backend process status:"
ps aux | grep "uvicorn main:app" | grep -v grep

echo ""
echo "To view backend logs, you have these options:"
echo ""
echo "1. If backend is running in a terminal window, check that terminal"
echo ""
echo "2. Restart backend with visible logs:"
echo "   cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend"
echo "   STOCKFISH_PATH=/opt/homebrew/bin/stockfish python3 -m uvicorn main:app --reload --port 8000"
echo ""
echo "3. Check recent startup log:"
echo "   tail -50 /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend/backend_startup.log"
echo ""
echo "4. If you want to run with logs saved to file, use:"
echo "   cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend"
echo "   STOCKFISH_PATH=/opt/homebrew/bin/stockfish python3 -m uvicorn main:app --reload --port 8000 2>&1 | tee backend.log"
echo "   Then in another terminal: tail -f backend.log"
