# Chess GPT Setup Instructions

## Overview
This project is a chess application with a FastAPI backend and Next.js frontend that integrates with ChatGPT for chess analysis and gameplay.

## What's Been Installed

### Backend Dependencies
- ✅ FastAPI (0.115.*)
- ✅ Uvicorn (0.30.*)
- ✅ Python Chess (1.999)
- ✅ Pydantic (2.*)
- ✅ Python-dotenv (1.*)
- ✅ Stockfish chess engine (compiled from source)

### Frontend Dependencies
- ✅ React (18.3.1)
- ✅ Next.js (14.2.18)
- ✅ React Chessboard (4.7.3)
- ✅ Chess.js (1.0.0-beta.8)
- ✅ OpenAI (4.67.3)
- ✅ Zod (3.23.8)
- ✅ TypeScript support

### Configuration
- ✅ OpenAI API key configured in `.env` file
- ✅ Stockfish engine compiled and ready
- ✅ Node.js 20.11.0 installed locally

## How to Run the Application

### 🎯 **RECOMMENDED: Single Command Startup**
```bash
# Start both backend and frontend with one command
./start.sh
```

### Alternative Options:

**Option 1: With Live Logs**
```bash
# Start both services with organized log output
./start_with_logs.sh
```

**Option 2: Simple One-liner**
```bash
# Minimal startup script
./run.sh
```

**Option 3: Separate Terminals**
```bash
# Terminal 1 - Start the backend
./start_backend.sh

# Terminal 2 - Start the frontend
./start_frontend.sh
```

**Option 4: Manual commands**
```bash
# Terminal 1 - Backend
cd backend
python3 main.py

# Terminal 2 - Frontend
cd frontend
export PATH=/Users/hugobosnic/Desktop/chess-gpt/node-v20.11.0-darwin-arm64/bin:$PATH
npm run dev
```

## Access the Application
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Important Notes

1. **Node.js Path**: The frontend requires the locally installed Node.js. The start script automatically sets the PATH, but if running manually, make sure to export the PATH as shown above.

2. **Stockfish**: The chess engine is compiled and ready to use. It's located at `backend/stockfish`.

3. **API Key**: Your OpenAI API key is configured in `backend/.env`. The key is set up and ready to use.

4. **Ports**: 
   - Backend runs on port 8000
   - Frontend runs on port 3000

## Troubleshooting

### If you get "command not found" errors:
- For Python: Make sure you're using `python3` instead of `python`
- For Node.js: Make sure to export the PATH as shown in the manual commands

### If the backend fails to start:
- Check that Stockfish is executable: `ls -la backend/stockfish`
- Verify the .env file exists: `ls -la backend/.env`

### If the frontend fails to start:
- Make sure Node.js is in the PATH: `export PATH=/Users/hugobosnic/Desktop/chess-gpt/node-v20.11.0-darwin-arm64/bin:$PATH`
- Check that dependencies are installed: `cd frontend && npm list`

## Project Structure
```
chess-gpt/
├── backend/
│   ├── main.py          # FastAPI application
│   ├── requirements.txt # Python dependencies
│   ├── .env            # Environment variables (API key)
│   ├── stockfish       # Chess engine binary
│   └── tactics.json    # Chess puzzles data
├── frontend/
│   ├── app/            # Next.js app directory
│   ├── components/     # React components
│   ├── lib/           # Utility functions
│   └── package.json   # Node.js dependencies
├── start.sh            # 🎯 Main startup script (both services)
├── start_with_logs.sh  # Startup with organized logs
├── run.sh              # Simple one-liner startup
├── start_backend.sh    # Backend-only startup script
├── start_frontend.sh   # Frontend-only startup script
└── node-v20.11.0-darwin-arm64/ # Local Node.js installation
```

## Next Steps
1. Run both the backend and frontend
2. Open http://localhost:3000 in your browser
3. Start playing chess with AI analysis!
