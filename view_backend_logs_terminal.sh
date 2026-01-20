#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_LOG="$SCRIPT_DIR/backend_live.log"

echo "🔍 Opening terminal to view backend logs..."
echo "Log file: $BACKEND_LOG"
echo ""

# Check if backend is running
if ! lsof -ti:8000 > /dev/null 2>&1; then
    echo "⚠️  Backend is not running on port 8000"
    echo "   Start it first with: ./start_all.sh or ./start_backend.sh"
    echo ""
fi

# Check if log file exists
if [ ! -f "$BACKEND_LOG" ]; then
    echo "⚠️  Log file not found: $BACKEND_LOG"
    echo "   Backend may not be running with logging enabled"
    echo "   Start backend with: ./start_all.sh"
    echo ""
fi

# Open a new terminal window to view backend logs (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    osascript -e "tell application \"Terminal\" to do script \"cd '$SCRIPT_DIR' && echo '📝 Backend Logs (Press Ctrl+C to exit)' && echo '' && tail -f '$BACKEND_LOG'\""
    echo "✅ Terminal window opened for backend logs"
    echo "   The log viewer will follow the backend log file in real-time"
else
    echo "Opening log viewer..."
    tail -f "$BACKEND_LOG"
fi
