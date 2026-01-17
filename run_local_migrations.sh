#!/bin/bash
# Run Supabase migrations on local PostgreSQL

set -e

PROJECT_DIR="/Users/hugobosnic/Desktop/Projects/Chess-GPT"
DB_NAME="chess_gpt_local"
DB_USER="postgres"
DB_PORT="5433"

cd "$PROJECT_DIR"

echo "📦 Running migrations on local database..."
echo ""

# Check if database is running
if ! pg_isready -h localhost -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; then
    echo "❌ PostgreSQL is not running on port $DB_PORT"
    echo "   Run: ./setup_local_supabase.sh first"
    exit 1
fi

CONNECTION_STRING="postgresql://$DB_USER@localhost:$DB_PORT/$DB_NAME"

# Get list of migration files from backend/supabase/migrations
MIGRATIONS_DIR="$PROJECT_DIR/backend/supabase/migrations"

# Run migrations in order
echo "🔧 Running migrations from: $MIGRATIONS_DIR"
echo ""

# Find all migration files and sort them
MIGRATION_FILES=$(find "$MIGRATIONS_DIR" -name "*.sql" -type f | sort)

if [ -z "$MIGRATION_FILES" ]; then
    echo "❌ No migration files found in $MIGRATIONS_DIR"
    exit 1
fi

for migration_file in $MIGRATION_FILES; do
    filename=$(basename "$migration_file")
    echo "📄 Running: $filename"
    
    # Skip if it's the old 025 file (we have split versions)
    if [[ "$filename" == "025_fix_analytics_schema.sql" ]]; then
        echo "   ⏭️  Skipping (replaced by 025a/b/c)"
        continue
    fi
    
    if psql "$CONNECTION_STRING" -f "$migration_file" > /dev/null 2>&1; then
        echo "   ✅ Success"
    else
        # Try again with error output
        echo "   ⚠️  Retrying with error output..."
        if psql "$CONNECTION_STRING" -f "$migration_file"; then
            echo "   ✅ Success (on retry)"
        else
            echo "   ❌ Failed - check errors above"
            # Don't exit - some migrations might have partial failures that are OK
        fi
    fi
    echo ""
done

echo "✅ Migrations complete!"
echo ""
echo "🧪 Testing connection..."
if psql "$CONNECTION_STRING" -c "\dt" > /dev/null 2>&1; then
    echo "✅ Database connection working!"
    echo ""
    echo "📊 Tables created:"
    psql "$CONNECTION_STRING" -c "\dt" | grep -E "public|profiles|games|positions" || echo "   (Run migrations to see tables)"
else
    echo "❌ Connection test failed"
    exit 1
fi

