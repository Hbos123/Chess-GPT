#!/bin/bash

echo "🚀 Starting Chess GPT Application..."
echo "=================================="

# Prefer a local backend virtualenv (avoids Homebrew PEP 668 + dependency drift).
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$ROOT_DIR/backend/.venv/bin/python"
if [ -x "$VENV_PY" ]; then
    PYTHON_BIN="$VENV_PY"
else
    PYTHON_BIN="python3"
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start backend in background
echo "📡 Starting backend server..."
cd backend
export BACKEND_PORT="${BACKEND_PORT:-8001}"
export ENABLE_DEBUG_LOGS="${ENABLE_DEBUG_LOGS:-true}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
BACKEND_LOG="${PWD}/backend.log"
echo "   ↪ backend log: ${BACKEND_LOG}"
# Truncate previous logs to avoid binary/NUL corruption breaking greps and diagnostics.
: > "${BACKEND_LOG}"
$PYTHON_BIN -u main.py > "${BACKEND_LOG}" 2>&1 &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start frontend in background
echo "🎨 Starting frontend server..."
cd frontend
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
# Allow override (e.g. Runpod proxy URL); default to local backend.
export NEXT_PUBLIC_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-http://localhost:${BACKEND_PORT:-8001}}"
FRONTEND_LOG="${PWD}/frontend.log"
echo "   ↪ frontend log: ${FRONTEND_LOG}"
: > "${FRONTEND_LOG}"
# Clear Next.js cache to fix 404 errors on static assets
if [ -d ".next" ]; then
    echo "   🧹 Clearing Next.js cache..."
    rm -rf .next
fi
npm run dev > "${FRONTEND_LOG}" 2>&1 &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Both services are starting up!"
echo "=================================="
FRONTEND_URL="http://localhost:3000"
FRONTEND_NET_URL=""
# Detect actual Next.js dev port (it may auto-bump if 3000 is taken).
for i in {1..50}; do
    if grep -q "Local:" "${ROOT_DIR}/frontend/frontend.log" 2>/dev/null; then
        FRONTEND_URL="$(grep -m1 "Local:" "${ROOT_DIR}/frontend/frontend.log" | awk '{print $3}')"
        FRONTEND_NET_URL="$(grep -m1 "Network:" "${ROOT_DIR}/frontend/frontend.log" | awk '{print $3}')"
        break
    fi
    sleep 0.1
done
echo "🌐 Frontend: ${FRONTEND_URL}"
if [ -n "${FRONTEND_NET_URL}" ]; then
    echo "📱 Frontend (LAN): ${FRONTEND_NET_URL}"
fi
echo "🔧 Backend API: http://localhost:${BACKEND_PORT:-8001}"
echo "📚 API Docs: http://localhost:${BACKEND_PORT:-8001}/docs"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
