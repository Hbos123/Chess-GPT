#!/bin/bash

echo "🔍 Chess GPT Status Check"
echo "========================"

# Check backend
echo -n "📡 Backend (port 8000): "
if curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo "✅ Running"
    echo "   API Response: $(curl -s http://localhost:8000/ | jq -r '.message' 2>/dev/null || echo 'Connected')"
else
    echo "❌ Not responding"
fi

# Check frontend
echo -n "🎨 Frontend (port 3000): "
if curl -s http://localhost:3000/ > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not responding"
fi

# Check Stockfish
echo -n "♟️  Stockfish Engine: "
if [ -f "backend/stockfish" ] && [ -x "backend/stockfish" ]; then
    echo "✅ Available"
else
    echo "❌ Missing or not executable"
fi

# Check API key
echo -n "🔑 OpenAI API Key: "
if [ -f "backend/.env" ] && grep -q "OPENAI_API_KEY" backend/.env; then
    echo "✅ Configured"
else
    echo "❌ Not configured"
fi

echo ""
echo "🌐 Access URLs:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
