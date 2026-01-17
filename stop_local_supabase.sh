#!/bin/bash
# Stop local Supabase PostgreSQL server

PROJECT_DIR="/Users/hugobosnic/Desktop/Projects/Chess-GPT"
DATA_DIR="$PROJECT_DIR/data/supabase_local"
PID_FILE="$DATA_DIR/postgres.pid"

if [ -f "$PID_FILE" ]; then
    PG_PID=$(cat "$PID_FILE")
    if kill -0 "$PG_PID" 2>/dev/null; then
        echo "🛑 Stopping PostgreSQL (PID: $PG_PID)..."
        kill "$PG_PID"
        sleep 2
        if kill -0 "$PG_PID" 2>/dev/null; then
            echo "   Force killing..."
            kill -9 "$PG_PID"
        fi
        rm "$PID_FILE"
        echo "✅ PostgreSQL stopped"
    else
        echo "⚠️  Process $PG_PID not running"
        rm "$PID_FILE"
    fi
else
    echo "⚠️  PID file not found. Trying to find and kill PostgreSQL on port 5433..."
    PIDS=$(lsof -ti:5433 2>/dev/null || echo "")
    if [ -n "$PIDS" ]; then
        echo "$PIDS" | xargs kill
        echo "✅ Killed PostgreSQL processes on port 5433"
    else
        echo "❌ No PostgreSQL process found on port 5433"
    fi
fi

