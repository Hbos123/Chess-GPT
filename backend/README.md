# Chess GPT Backend

FastAPI backend for Chess GPT with python-chess and Stockfish integration.

## Prerequisites

- Python 3.11+
- Stockfish chess engine binary

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Download and place Stockfish:
   - Download Stockfish from https://stockfishchess.org/download/
   - Extract the binary
   - Place it at `backend/stockfish` (or anywhere and set `STOCKFISH_PATH` env var)
   - Make it executable: `chmod +x stockfish` (Unix/Mac)

## Configuration

Create a `.env` file (optional) if you want to customize settings:

```bash
STOCKFISH_PATH=./stockfish
OPENAI_API_KEY=sk-your-openai-key
# Set CG_FAKE_VISION=1 to bypass photo recognition during local testing
CG_FAKE_VISION=0
```

Or set the environment variable when running:
```bash
STOCKFISH_PATH=/path/to/stockfish uvicorn main:app --reload --port 8000
```

## Running the Server

```bash
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- Interactive docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## Endpoints

- `GET /meta` - API metadata and system prompt
- `GET /analyze_position` - Analyze a position (FEN, lines, depth)
- `POST /play_move` - Make a move and get engine response
- `GET /opening_lookup` - Look up opening information (stub)
- `POST /vision/board` - Send a board photo and receive the detected FEN (uses GPT-4o-mini vision)
- `GET /tactics_next` - Get next tactics puzzle
- `POST /annotate` - Save/validate annotations

## Tactics Puzzles

Edit `tactics.json` to add more puzzles. Each puzzle should have:
- `id`: Unique identifier
- `rating`: Difficulty rating (1200-2400)
- `fen`: Position in FEN notation
- `side_to_move`: "w" or "b"
- `prompt`: Description for the user
- `solution_pv_san`: Solution in SAN notation
- `themes`: Array of tactical themes

## Troubleshooting

**Engine not found:**
- Ensure Stockfish binary is in the correct location
- Check file permissions (must be executable)
- Verify `STOCKFISH_PATH` environment variable

**CORS errors:**
- Backend is configured for `http://localhost:3000`
- If frontend runs on different port, update CORS settings in `main.py`

**Analysis errors:**
- Ensure Stockfish is working: `./stockfish` should start the engine
- Check depth and time limits aren't too aggressive
- Some engines don't support UCI_Elo strength limiting

