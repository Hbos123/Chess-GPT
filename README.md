# Chess GPT

A minimal, clean, fully working "ChatGPT for Chess" that combines chess engine analysis with LLM-powered natural language explanations. Play, analyze, solve tactics, and discuss chess concepts with AI assistance.

## Features

- 🎮 **PLAY Mode** - Play against Stockfish engine with adjustable strength
- 📊 **ANALYZE Mode** - Deep position analysis with candidates, threats, and themes
- 🧩 **TACTICS Mode** - Solve chess puzzles with varying difficulty
- 💬 **DISCUSS Mode** - Chat about chess strategies, plans, and principles
- 📝 **Annotations** - Add comments, arrows, and highlights to positions
- 🤖 **LLM Integration** - Natural language explanations via OpenAI API
- 📋 **PGN Export** - Save and share your games

## Stack

**Backend:**
- FastAPI - Modern Python web framework
- python-chess - Chess logic and move validation
- Stockfish - UCI chess engine for analysis
- Pydantic - Data validation

**Frontend:**
- Next.js 14 - React framework with App Router
- TypeScript - Type safety
- react-chessboard - Interactive chess board
- OpenAI SDK - LLM integration

## Prerequisites

- **Node.js 18+** (for frontend)
- **Python 3.11+** (for backend)
- **Stockfish** chess engine binary
- **OpenAI API key** (for LLM features)

## Quick Start

### 1. Clone or Extract

```bash
cd chess-gpt
```

### 2. Backend Setup

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Download Stockfish
# macOS (via Homebrew):
brew install stockfish
# Then create symlink:
ln -s $(which stockfish) ./stockfish

# Or download from https://stockfishchess.org/download/
# Place the binary at backend/stockfish and make it executable:
# chmod +x stockfish

# Verify Stockfish works
./stockfish
# (type 'quit' to exit)

# Start backend server
uvicorn main:app --reload --port 8000
```

Backend will be available at `http://localhost:8000`

### 3. Frontend Setup

Open a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Create environment file
cp .env.local.example .env.local

# Edit .env.local and add your OpenAI API key:
# NEXT_PUBLIC_OPENAI_API_KEY=sk-your-actual-key

# Start frontend
npm run dev
```

Frontend will be available at `http://localhost:3000`

### 4. Open Browser

Navigate to `http://localhost:3000` and start playing!

## Configuration

### Backend Environment Variables

Create `backend/.env` (optional):

```bash
STOCKFISH_PATH=./stockfish
```

Or set when running:
```bash
STOCKFISH_PATH=/usr/local/bin/stockfish uvicorn main:app --reload --port 8000
```

### Frontend Environment Variables

Edit `frontend/.env.local`:

```bash
# Backend API URL
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# OpenAI API key (required for LLM features)
NEXT_PUBLIC_OPENAI_API_KEY=sk-your-key-here

# OpenAI model (optional, defaults to gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini
```

⚠️ **Security Note:** For local development only. The OpenAI key is exposed client-side. For production, implement a backend proxy.

## Usage Guide

### PLAY Mode

1. Select **PLAY** from the mode dropdown
2. Make moves by dragging pieces on the board
3. Engine responds automatically (1600 ELO by default)
4. View evaluation and commentary in chat
5. PGN updates automatically

### ANALYZE Mode

1. Set up a position or continue from current position
2. Click **"📊 Analyze Position"** button
3. Receive detailed analysis:
   - Centipawn evaluation
   - Win probability
   - Top 3 candidate moves with variations
   - Tactical threats
   - Piece quality assessment
   - Strategic themes
4. Optional: LLM provides natural language explanation

### TACTICS Mode

1. Select **TACTICS** from the mode dropdown
2. Click **"🧩 Next Tactic"** button
3. Study the position and find the best move
4. Try to solve by making moves
5. Click **"💡 Reveal Solution"** if stuck
6. See the complete solution variation

### DISCUSS Mode

1. Select **DISCUSS** from the mode dropdown
2. Ask questions about:
   - Chess strategies and plans
   - Opening principles
   - Endgame techniques
   - Positional concepts
3. Get explanations backed by engine analysis when needed

### Additional Features

- **Copy PGN**: Export game notation
- **Reset Board**: Start fresh position
- **Toggle LLM**: Turn on/off natural language responses
- **Board Flip**: Automatic in tactics mode

## Architecture

### Backend Endpoints

- `GET /meta` - API metadata and system prompt
- `GET /analyze_position?fen=...&lines=3&depth=16` - Position analysis
- `POST /play_move` - Make move and get engine response
- `GET /opening_lookup?fen=...` - ECO opening lookup (stub)
- `GET /tactics_next?rating_min=1200&rating_max=2000` - Fetch tactic puzzle
- `POST /annotate` - Save/validate annotations

### Frontend Components

- `page.tsx` - Main application with state management
- `Board.tsx` - Chess board with annotations rendering
- `Chat.tsx` - Chat interface with message history
- `ModeChip.tsx` - Mode selector dropdown
- `RouterHint.tsx` - Mode routing indicator
- `lib/api.ts` - Backend API client
- `types/index.ts` - TypeScript definitions

### Data Flow

1. User interacts with board or chat
2. Frontend calls backend API for engine analysis
3. Backend uses Stockfish for concrete evaluations
4. Frontend optionally calls OpenAI for natural language
5. Results displayed in chat and board annotations

## Customization

### Add More Tactics

Edit `backend/tactics.json`:

```json
{
  "id": "t007",
  "rating": 1800,
  "fen": "your-position-fen",
  "side_to_move": "w",
  "prompt": "Description of the tactic",
  "solution_pv_san": "Qxh7+ Kxh7 Rh3+ Kg8 Rh8#",
  "themes": ["mate", "sacrifice"]
}
```

### Adjust Engine Strength

In `frontend/app/page.tsx`, modify the `playMove` call:

```typescript
const response = await playMove(game.fen(), moveSan, 2000, 1500);
//                                                    ^^^^ ELO rating
```

### Change Analysis Depth

Adjust depth parameter in `analyzePosition` calls:

```typescript
const result = await analyzePosition(fen, 3, 20);
//                                         ^   ^^ depth
//                                         lines
```

## Troubleshooting

### Backend won't start

**Error:** "Stockfish not found"
- Download Stockfish from https://stockfishchess.org/download/
- Place at `backend/stockfish`
- Make executable: `chmod +x backend/stockfish`
- Or set `STOCKFISH_PATH` environment variable

**Error:** "Module not found"
- Run `pip install -r requirements.txt`
- Ensure Python 3.11+: `python --version`

### Frontend won't start

**Error:** "Cannot find module"
- Run `npm install` in frontend directory
- Clear cache: `rm -rf .next node_modules && npm install`

**Error:** "OpenAI API key not configured"
- Create `.env.local` from `.env.local.example`
- Add valid OpenAI API key
- Restart dev server

### CORS errors

- Ensure backend is running on port 8000
- Ensure frontend is running on port 3000
- Check browser console for specific error
- Backend CORS is configured for http://localhost:3000

### Analysis returns no results

- Check Stockfish is working: `./backend/stockfish`
- Verify FEN is valid
- Check backend logs for errors
- Reduce depth if timeout occurs

### Moves not registering

- Ensure move is legal
- Check if waiting for engine response
- Verify board is not disabled (tactics mode)
- Try resetting board

## API Documentation

Once backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Performance Notes

- **Analysis depth 16-20**: Good balance of speed/accuracy
- **Play mode depth 12**: Fast responses (~1-2 seconds)
- **Threat detection depth 10**: Quick tactical scans
- **Engine strength**: UCI_Elo 1200-2400 range

## Limitations (MVP)

- In-memory only (no database persistence)
- Opening book is stubbed (returns empty)
- Single user (no multiplayer)
- Basic annotations (no full PGN editing)
- Client-side OpenAI key (not production-ready)

## Future Enhancements

- Database persistence (PostgreSQL)
- Opening book integration (polyglot/lichess)
- Multi-game management
- Advanced PGN editor with variations
- User accounts and game history
- Multiplayer support
- Mobile-responsive board
- Backend OpenAI proxy for security
- Puzzle rating system with spaced repetition
- Game analysis workflow (upload PGN, analyze all moves)

## Credits

- **Stockfish** - Open source chess engine
- **python-chess** - Python chess library
- **react-chessboard** - React chess board component
- **OpenAI** - Language model API
- **FastAPI** - Modern Python web framework
- **Next.js** - React framework

## License

This is a demo/educational project. Use freely for learning and experimentation.

## Support

For issues or questions:
1. Check this README
2. Review backend/frontend READMEs
3. Check API documentation at /docs
4. Inspect browser console and backend logs

---

Built with ♟️ by combining the power of chess engines and large language models.

