#!/bin/bash
# Clean restart script that clears Python cache and restarts the server

echo "🧹 Clearing Python cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
find . -name "*.pyo" -delete 2>/dev/null
echo "✅ Cache cleared"

echo ""
echo "🔍 Checking syntax..."
python3 check_syntax.py confidence_engine.py
if [ $? -ne 0 ]; then
    echo "❌ Syntax errors found! Fix them before restarting."
    exit 1
fi

echo ""
echo "🔄 Restarting server..."
# Kill existing server if running
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 1

# Start server
echo "✅ Starting server..."
exec python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

