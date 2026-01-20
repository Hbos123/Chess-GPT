#!/bin/bash

echo "🛑 Stopping existing servers..."
lsof -ti:8001 -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 2

echo "📡 Starting backend..."
cd backend
export BACKEND_PORT="${BACKEND_PORT:-8001}"
if [ -x ".venv/bin/python" ]; then
    .venv/bin/python main.py > ../backend.log 2>&1 &
else
    python3 main.py > ../backend.log 2>&1 &
fi
BACKEND_PID=$!
cd ..
echo "Backend PID: $BACKEND_PID"

sleep 3

echo "🎨 Starting frontend..."
cd frontend
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
export NEXT_PUBLIC_BACKEND_URL="http://localhost:8001"
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "Frontend PID: $FRONTEND_PID"

sleep 5

echo ""
echo "✅ Servers started!"
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend: http://localhost:8001"
echo ""
echo "Check logs:"
echo "  tail -f backend.log"
echo "  tail -f frontend.log"
echo ""
echo "To stop: kill $BACKEND_PID $FRONTEND_PID"

