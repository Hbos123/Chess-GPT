#!/bin/bash
# Configure environment for local Supabase

PROJECT_DIR="/Users/hugobosnic/Desktop/Projects/Chess-GPT"
LOCAL_CONNECTION="postgresql://postgres@localhost:5433/chess_gpt_local"

cd "$PROJECT_DIR"

echo "🔧 Configuring local Supabase..."
echo ""

# Update backend/.env
BACKEND_ENV="$PROJECT_DIR/backend/.env"
if [ -f "$BACKEND_ENV" ]; then
    # Add or update LOCAL_POSTGRES_URL
    if grep -q "LOCAL_POSTGRES_URL" "$BACKEND_ENV"; then
        sed -i '' "s|LOCAL_POSTGRES_URL=.*|LOCAL_POSTGRES_URL=$LOCAL_CONNECTION|" "$BACKEND_ENV"
        echo "✅ Updated LOCAL_POSTGRES_URL in backend/.env"
    else
        echo "" >> "$BACKEND_ENV"
        echo "# Local PostgreSQL (for development)" >> "$BACKEND_ENV"
        echo "LOCAL_POSTGRES_URL=$LOCAL_CONNECTION" >> "$BACKEND_ENV"
        echo "✅ Added LOCAL_POSTGRES_URL to backend/.env"
    fi
    
    # Comment out remote Supabase (optional - uncomment to switch back)
    if grep -q "^SUPABASE_URL=" "$BACKEND_ENV" && ! grep -q "^#SUPABASE_URL=" "$BACKEND_ENV"; then
        echo ""
        echo "💡 To use local database, you can comment out remote Supabase:"
        echo "   # Comment these lines in backend/.env:"
        echo "   # SUPABASE_URL=..."
        echo "   # SUPABASE_SERVICE_ROLE_KEY=..."
    fi
else
    echo "⚠️  backend/.env not found. Creating..."
    cat > "$BACKEND_ENV" << EOF
# Local PostgreSQL (for development)
LOCAL_POSTGRES_URL=$LOCAL_CONNECTION

# Remote Supabase (commented out for local development)
# SUPABASE_URL=https://cbskaefmgmcyhrblsgez.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=...
EOF
    echo "✅ Created backend/.env with local configuration"
fi

# Update frontend/.env.local (for local auth - optional)
FRONTEND_ENV="$PROJECT_DIR/frontend/.env.local"
if [ -f "$FRONTEND_ENV" ]; then
    echo ""
    echo "💡 Frontend auth: For local development, you may want to:"
    echo "   1. Keep using remote Supabase for auth (recommended)"
    echo "   2. Or set up local Supabase CLI for full local stack"
    echo "   (Local auth requires Supabase CLI with Docker)"
else
    echo ""
    echo "💡 Frontend: Using remote Supabase for auth is fine"
    echo "   (Backend will use local PostgreSQL for data)"
fi

echo ""
echo "✅ Configuration complete!"
echo ""
echo "📊 Local Database Info:"
echo "   Connection: $LOCAL_CONNECTION"
echo "   Data stored in: $PROJECT_DIR/data/supabase_local"
echo ""
echo "🚀 Next steps:"
echo "   1. Restart backend: cd backend && python3 main.py"
echo "   2. Backend will automatically use local PostgreSQL"
echo "   3. Frontend can still use remote Supabase for auth"
echo ""

