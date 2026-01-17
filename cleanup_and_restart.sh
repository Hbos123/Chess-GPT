#!/bin/bash
# Comprehensive cleanup script - removes cache files and corrupted artifacts
# Safe to run - only deletes cache/build files, not your source code

set -e  # Exit on error

echo "🧹 Chess-GPT Cleanup and Restart Script"
echo "========================================"
echo ""

# Step 1: Stop running services
echo "🛑 Stopping running services..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "  (No backend process found)"
lsof -ti:3000 | xargs kill -9 2>/dev/null || echo "  (No frontend process found)"
sleep 2
echo "✅ Services stopped"
echo ""

# Step 2: Clean Python cache files
echo "🐍 Cleaning Python cache files..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend

# Remove __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "  ✓ Removed __pycache__ directories"

# Remove .pyc files
find . -name "*.pyc" -delete 2>/dev/null || true
echo "  ✓ Removed .pyc files"

# Remove .pyo files
find . -name "*.pyo" -delete 2>/dev/null || true
echo "  ✓ Removed .pyo files"

# Remove .pyc files in parent directories too
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

echo "✅ Python cache cleaned"
echo ""

# Step 3: Clean frontend cache files
echo "⚛️  Cleaning frontend cache files..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend

# Remove Next.js build cache
if [ -d ".next" ]; then
    rm -rf .next
    echo "  ✓ Removed .next directory"
fi

# Remove TypeScript build info
if [ -f "tsconfig.tsbuildinfo" ]; then
    rm -f tsconfig.tsbuildinfo
    echo "  ✓ Removed tsconfig.tsbuildinfo"
fi

# Remove node_modules cache (but keep node_modules itself)
if [ -d "node_modules/.cache" ]; then
    rm -rf node_modules/.cache
    echo "  ✓ Removed node_modules/.cache"
fi

echo "✅ Frontend cache cleaned"
echo ""

# Step 4: Ask about reinstalling dependencies
echo "📦 Dependency reinstallation options:"
echo ""
echo "Would you like to reinstall dependencies? (This will fix corrupted packages)"
echo "  1) Reinstall backend Python packages"
echo "  2) Reinstall frontend Node packages"
echo "  3) Reinstall both"
echo "  4) Skip (just clean cache)"
echo ""
read -p "Enter choice (1-4) [default: 4]: " choice
choice=${choice:-4}

if [ "$choice" = "1" ] || [ "$choice" = "3" ]; then
    echo ""
    echo "📥 Reinstalling backend Python packages..."
    cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
    pip3 install --upgrade pip 2>/dev/null || true
    pip3 install -r requirements.txt --force-reinstall --no-cache-dir
    echo "✅ Backend packages reinstalled"
    echo ""
fi

if [ "$choice" = "2" ] || [ "$choice" = "3" ]; then
    echo ""
    echo "📥 Reinstalling frontend Node packages..."
    cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
    # Check if we should remove node_modules entirely
    read -p "Remove node_modules and do a fresh install? (y/N): " fresh_install
    if [[ "$fresh_install" =~ ^[Yy]$ ]]; then
        rm -rf node_modules
        rm -f package-lock.json
        echo "  ✓ Removed node_modules and package-lock.json"
    fi
    npm install
    echo "✅ Frontend packages reinstalled"
    echo ""
fi

# Step 5: Restart services
echo "🚀 Restarting services..."
echo ""

# Start backend
echo "📡 Starting backend..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 > /tmp/chess_backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"
sleep 3

# Start frontend
echo "🎨 Starting frontend..."
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
npm run dev > /tmp/chess_frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"
sleep 3

# Verify services are running
echo ""
echo "🔍 Verifying services..."
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "  ✅ Backend is running on port 8000"
else
    echo "  ❌ Backend failed to start - check logs: tail -f /tmp/chess_backend.log"
fi

if lsof -ti:3000 > /dev/null 2>&1; then
    echo "  ✅ Frontend is running on port 3000"
else
    echo "  ❌ Frontend failed to start - check logs: tail -f /tmp/chess_frontend.log"
fi

echo ""
echo "========================================"
echo "✅ Cleanup and restart complete!"
echo ""
echo "📊 View backend logs:"
echo "   tail -f /tmp/chess_backend.log"
echo ""
echo "📊 View frontend logs:"
echo "   tail -f /tmp/chess_frontend.log"
echo ""
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo ""

















