#!/bin/bash

# Kill existing processes
echo "Killing existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
sleep 2

# Start backend
echo "Starting backend on port 8000..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to start
sleep 3

# Start frontend
echo "Starting frontend on port 3000..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
npx next dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# Wait a bit
sleep 5

# Check status
echo ""
echo "Checking server status..."
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "✅ Backend is running on port 8000"
else
    echo "❌ Backend failed to start"
fi

if lsof -ti:3000 > /dev/null 2>&1; then
    echo "✅ Frontend is running on port 3000"
else
    echo "❌ Frontend failed to start"
fi

echo ""
echo "Servers started. Check http://localhost:3000 for frontend"
echo "Backend logs: Check terminal or /tmp/backend.log"
echo "Frontend logs: Check terminal or /tmp/frontend.log"

