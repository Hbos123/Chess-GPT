#!/bin/bash
# Setup Local Supabase Alternative using PostgreSQL
# Data will persist in ./data/supabase_local/

set -e

PROJECT_DIR="/Users/hugobosnic/Desktop/Projects/Chess-GPT"
DATA_DIR="$PROJECT_DIR/data/supabase_local"
DB_NAME="chess_gpt_local"
DB_USER="postgres"
DB_PORT="5433"  # Use 5433 to avoid conflicts with system PostgreSQL

cd "$PROJECT_DIR"

echo "🚀 Setting up Local Supabase Alternative"
echo "📁 Data directory: $DATA_DIR"
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL not found. Installing..."
    brew install postgresql@14
    echo "✅ PostgreSQL installed"
fi

# Check if initdb exists
INITDB_PATH=$(brew --prefix postgresql@14)/bin/initdb 2>/dev/null || which initdb
if [ -z "$INITDB_PATH" ]; then
    echo "❌ initdb not found. Please install PostgreSQL."
    exit 1
fi

# Create data directory
echo "📁 Creating data directory..."
mkdir -p "$DATA_DIR"

# Initialize database if it doesn't exist
if [ ! -f "$DATA_DIR/PG_VERSION" ]; then
    echo "🔧 Initializing PostgreSQL database..."
    "$INITDB_PATH" -D "$DATA_DIR" -U "$DB_USER" --locale=C --encoding=UTF8
    echo "✅ Database initialized"
else
    echo "✅ Database already initialized"
fi

# Start PostgreSQL server
echo "🔄 Starting PostgreSQL server..."
PGDATA="$DATA_DIR" postgres -D "$DATA_DIR" -p "$DB_PORT" > "$DATA_DIR/postgres.log" 2>&1 &
PG_PID=$!
echo "   PID: $PG_PID"
echo "   Port: $DB_PORT"

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 3

# Check if server is running
if ! kill -0 $PG_PID 2>/dev/null; then
    echo "❌ PostgreSQL failed to start. Check $DATA_DIR/postgres.log"
    exit 1
fi

# Create database if it doesn't exist
echo "📦 Creating database '$DB_NAME'..."
PGPASSWORD="" psql -h localhost -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || echo "   Database may already exist"

# Get connection string
CONNECTION_STRING="postgresql://$DB_USER@localhost:$DB_PORT/$DB_NAME"

echo ""
echo "✅ Local PostgreSQL is running!"
echo ""
echo "📊 Connection Info:"
echo "   Host: localhost"
echo "   Port: $DB_PORT"
echo "   Database: $DB_NAME"
echo "   User: $DB_USER"
echo "   Connection: $CONNECTION_STRING"
echo ""
echo "📝 Next steps:"
echo "   1. Run migrations: ./run_local_migrations.sh"
echo "   2. Update .env files with local connection"
echo ""
echo "💾 Data is stored in: $DATA_DIR"
echo "🛑 To stop: kill $PG_PID or run: ./stop_local_supabase.sh"

# Save PID for later
echo "$PG_PID" > "$DATA_DIR/postgres.pid"

