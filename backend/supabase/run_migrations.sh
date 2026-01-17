#!/bin/bash
# Script to run Supabase migrations via CLI
# Usage: ./run_migrations.sh

set -e

echo "🚀 Running Supabase migrations via CLI..."
echo ""

# Check if supabase CLI is installed
if ! command -v supabase &> /dev/null; then
    echo "❌ Supabase CLI not found. Install with: brew install supabase/tap/supabase"
    exit 1
fi

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIGRATIONS_DIR="$SCRIPT_DIR/migrations"

# Check if migrations directory exists
if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "❌ Migrations directory not found: $MIGRATIONS_DIR"
    exit 1
fi

echo "📦 Executing migrations in order..."
echo ""

# Execute migrations one by one (in case one times out, we can retry individually)
echo "1️⃣ Running 025a_fix_analytics_schema_part1.sql (schema changes)..."
supabase db execute --file "$MIGRATIONS_DIR/025a_fix_analytics_schema_part1.sql" || {
    echo "⚠️  025a failed or timed out. You can retry it separately."
    read -p "Continue with 025b? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
}

echo ""
echo "2️⃣ Running 025b_fix_analytics_schema_part2.sql (v4 functions)..."
supabase db execute --file "$MIGRATIONS_DIR/025b_fix_analytics_schema_part2.sql" || {
    echo "⚠️  025b failed. Check the error above."
    exit 1
}

echo ""
echo "3️⃣ Running 025c_fix_analytics_schema_part3.sql (v3 functions)..."
supabase db execute --file "$MIGRATIONS_DIR/025c_fix_analytics_schema_part3.sql" || {
    echo "⚠️  025c failed. Check the error above."
    exit 1
}

echo ""
echo "✅ All migrations complete!"

