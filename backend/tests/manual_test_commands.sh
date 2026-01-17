#!/bin/bash

# Manual Test Commands for Chess GPT Backend
# Run these commands to verify system functionality

BASE_URL="http://localhost:${BACKEND_PORT:-8001}"

echo "==================================================================="
echo "Chess GPT Backend Manual Test Suite"
echo "==================================================================="
echo ""

# Test 1: Engine health
echo "📊 Test 1: Engine Health Check"
curl -s "$BASE_URL/meta" | jq '.name, .version'
echo ""

# Test 2: Engine metrics
echo "📊 Test 2: Engine Queue Metrics"
curl -s "$BASE_URL/engine/metrics" | jq '.'
echo ""

# Test 3: Position analysis
echo "📊 Test 3: Position Analysis (e4)"
curl -s "$BASE_URL/analyze_position?fen=rnbqkbnr%2Fpppppppp%2F8%2F8%2F4P3%2F8%2FPPPP1PPP%2FRNBQKBNR%20b%20KQkq%20e3%200%201&depth=12&lines=3" | jq '.eval_cp, .candidate_moves | length'
echo ""

# Test 4: Play move
echo "📊 Test 4: Play Move (e4 with engine response)"
curl -X POST "$BASE_URL/play_move" \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "user_move_san": "e4",
    "engine_elo": 1600,
    "time_ms": 1000
  }' | jq '.engine_move_san, .commentary'
echo ""

# Test 5: Confidence tree (move)
echo "📊 Test 5: Confidence Tree (Nf3)"
curl -X POST "$BASE_URL/confidence/raise_move" \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "move_san": "Nf3",
    "target": 80
  }' | jq '.overall_confidence, .line_confidence, .nodes | length'
echo ""

# Test 6: Engine queue stress test
echo "📊 Test 6: Concurrent Request Stress Test"
for i in {1..5}; do
  curl -s "$BASE_URL/analyze_position?fen=rnbqkbnr%2Fpppppppp%2F8%2F8%2F4P3%2F8%2FPPPP1PPP%2FRNBQKBNR%20b%20KQkq%20-%200%201&depth=10&lines=2" > /dev/null &
done
wait
echo "All 5 concurrent requests completed"
curl -s "$BASE_URL/engine/metrics" | jq '.total_requests, .failed_requests, .max_queue_depth'
echo ""

# Test 7: LLM Chat
echo "📊 Test 7: LLM Chat"
curl -X POST "$BASE_URL/llm_chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Analyze e4"}],
    "context": {
      "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "pgn": "1. e4"
    },
    "use_tools": false
  }' | jq '.content' | head -20
echo ""

echo "==================================================================="
echo "✅ Manual test suite complete"
echo "==================================================================="

