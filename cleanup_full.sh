#!/bin/bash
# Full automatic cleanup - removes all cache files and reinstalls dependencies
# No prompts - does everything automatically

set -e

echo "🧹 Full Automatic Cleanup"
echo "=========================="
echo ""

# Stop services
echo "🛑 Stopping services..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
sleep 2

# Clean Python cache
echo "🐍 Cleaning Python cache..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
echo "✅ Python cache cleaned"

# Clean frontend cache
echo "⚛️  Cleaning frontend cache..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
rm -rf .next 2>/dev/null || true
rm -f tsconfig.tsbuildinfo 2>/dev/null || true
rm -rf node_modules/.cache 2>/dev/null || true
echo "✅ Frontend cache cleaned"

# Reinstall backend packages
echo "📥 Reinstalling backend packages..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
pip3 install --upgrade pip 2>/dev/null || true
pip3 install -r requirements.txt --force-reinstall --no-cache-dir
echo "✅ Backend packages reinstalled"

# Reinstall frontend packages (without removing node_modules to be safe)
echo "📥 Reinstalling frontend packages..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
npm install
echo "✅ Frontend packages reinstalled"

# Restart services
echo "🚀 Restarting services..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 > /tmp/chess_backend.log 2>&1 &
sleep 3

cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
npm run dev > /tmp/chess_frontend.log 2>&1 &
sleep 3

echo ""
echo "✅ Cleanup complete! Services restarted."
echo ""
echo "View backend logs: tail -f /tmp/chess_backend.log"


















