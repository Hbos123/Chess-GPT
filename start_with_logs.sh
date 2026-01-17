#!/bin/bash

echo "🚀 Starting Chess GPT Application with Live Logs..."
echo "=================================================="

# Create named pipes for logging
BACKEND_LOG="/tmp/chess_backend.log"
FRONTEND_LOG="/tmp/chess_frontend.log"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    rm -f $BACKEND_LOG $FRONTEND_LOG
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start backend
echo "📡 Starting backend server..."
cd backend
python3 main.py > $BACKEND_LOG 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend
echo "🎨 Starting frontend server..."
cd frontend
export NEXT_PUBLIC_BACKEND_URL="http://localhost:8000"
npm run dev > $FRONTEND_LOG 2>&1 &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Services started! Live logs below:"
echo "====================================="
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

# Function to display logs with prefixes
tail_logs() {
    tail -f $BACKEND_LOG | sed 's/^/[BACKEND] /' &
    tail -f $FRONTEND_LOG | sed 's/^/[FRONTEND] /' &
    wait
}

# Start log monitoring
tail_logs
