#!/bin/bash
# Helper script to view backend logs

echo "🔍 Checking for backend logs..."
echo ""

# Check if backend is running
if ! lsof -ti:8000 > /dev/null 2>&1; then
    echo "❌ Backend is not running on port 8000"
    exit 1
fi

echo "✅ Backend is running on port 8000"
echo ""

# Check for log files
if [ -f "backend/backend.log" ]; then
    echo "📄 Found backend/backend.log (may be from previous session)"
    echo "   Last modified: $(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" backend/backend.log 2>/dev/null || stat -c "%y" backend/backend.log 2>/dev/null || echo "unknown")"
    echo ""
fi

if [ -f "backend_live.log" ]; then
    echo "📄 Found backend_live.log"
    echo "   Last modified: $(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" backend_live.log 2>/dev/null || stat -c "%y" backend_live.log 2>/dev/null || echo "unknown")"
    echo ""
fi

# Show options
echo "Options to view logs:"
echo ""
echo "1. If you started backend with start_servers.sh, check that terminal"
echo ""
echo "2. View the log file (if it exists):"
echo "   tail -f backend/backend.log"
echo "   or"
echo "   tail -f backend_live.log"
echo ""
echo "3. Restart backend with logging to file:"
echo "   cd backend && source .venv/bin/activate && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 > ../backend_live.log 2>&1 &"
echo "   Then: tail -f ../backend_live.log"
echo ""
echo "4. Test validation endpoint directly:"
echo "   curl 'http://localhost:8000/profile/validate-account?username=YOUR_USERNAME&platform=chess.com'"
echo ""

# If backend_live.log exists, offer to tail it
if [ -f "backend_live.log" ]; then
    echo "Would you like to tail backend_live.log now? (y/n)"
    read -r response
    if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
        tail -f backend_live.log
    fi
fi
