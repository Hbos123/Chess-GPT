#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BACKEND_LOG="$PROJECT_ROOT/backend_live.log"

echo "🚀 Starting Chess GPT Application..."
echo "===================================="
echo "Project root: $PROJECT_ROOT"
echo ""

# Kill any existing processes
echo "🧹 Cleaning up existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
sleep 2

# Start backend with logging
echo "📡 Starting backend server on port 8000..."
cd "$BACKEND_DIR"

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "✅ Activated virtual environment"
fi

# Start backend with logging to file
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2 > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"
echo "   Logs: $BACKEND_LOG"

# Wait for backend to start
sleep 3

# Start frontend
echo ""
echo "🎨 Starting frontend server on port 3000..."
cd "$FRONTEND_DIR"

# Set backend URL
export NEXT_PUBLIC_BACKEND_URL="http://localhost:8000"

# Start frontend
npm run dev > "$PROJECT_ROOT/frontend_live.log" 2>&1 &
FRONTEND_PID=$!
echo "✅ Frontend started (PID: $FRONTEND_PID)"
echo "   Logs: $PROJECT_ROOT/frontend_live.log"

# Wait a bit for servers to initialize
sleep 5

# Check status
echo ""
echo "📊 Server Status:"
echo "================="
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "✅ Backend is running on http://localhost:8000"
else
    echo "❌ Backend failed to start"
fi

if lsof -ti:3000 > /dev/null 2>&1; then
    echo "✅ Frontend is running on http://localhost:3000"
else
    echo "❌ Frontend failed to start"
fi

echo ""
echo "🌐 Access your application:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📝 Logs:"
echo "   Backend: $BACKEND_LOG"
echo "   Frontend: $PROJECT_ROOT/frontend_live.log"
echo ""
echo "💡 To view backend logs in a new terminal, run:"
echo "   tail -f \"$BACKEND_LOG\""
echo ""
echo "🛑 To stop servers, run:"
echo "   kill $BACKEND_PID $FRONTEND_PID"
echo "   or"
echo "   lsof -ti:8000 | xargs kill -9"
echo "   lsof -ti:3000 | xargs kill -9"
echo ""

# Open a new terminal window to view backend logs (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🔍 Opening new terminal window for backend logs..."
    osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && tail -f '$BACKEND_LOG'\""
    echo "✅ Terminal window opened for backend logs"
fi

# Keep script running
echo "Press Ctrl+C to stop both servers..."
wait
