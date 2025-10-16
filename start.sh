#!/bin/bash

echo "🚀 Starting Chess GPT Application..."
echo "=================================="

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
python3 main.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start frontend in background
echo "🎨 Starting frontend server..."
cd frontend
export PATH=/Users/hugobosnic/Desktop/chess-gpt/backend/node-v20.11.0-darwin-arm64/bin:$PATH
/Users/hugobosnic/Desktop/chess-gpt/backend/node-v20.11.0-darwin-arm64/bin/npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Both services are starting up!"
echo "=================================="
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
