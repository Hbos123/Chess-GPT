# ⚡ Command Cheat Sheet

Quick reference for all Chess-GPT commands.

---

## 🚀 FIRST TIME SETUP

```bash
# Navigate to project
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT

# Run the installer (does everything for you)
./install_commands.sh
```

---

## 🎮 RUNNING THE APP

### Start Everything (Recommended)
```bash
./start.sh
```
Starts both backend and frontend in one command.

### Alternative: Separate Terminals
```bash
# Terminal 1 - Backend
./start_backend.sh

# Terminal 2 - Frontend  
./start_frontend.sh
```

### Access URLs
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## 📊 MONITORING

### Check Status
```bash
./status.sh
```
Shows if backend and frontend are running.

### View Logs
```bash
./watch_backend_logs.sh
```

---

## 🛑 STOPPING THE APP

Press `Ctrl + C` in the terminal where services are running.

Or kill processes manually:
```bash
# Kill backend (port 8000)
lsof -ti:8000 | xargs kill -9

# Kill frontend (port 3000)
lsof -ti:3000 | xargs kill -9
```

---

## 🔧 TROUBLESHOOTING

### Check Installations
```bash
# Check Python
python3 --version

# Check Node.js
node --version
npm --version

# Check Stockfish
which stockfish
stockfish  # (type 'quit' to exit)

# Check Homebrew
brew --version
```

### Reinstall Dependencies
```bash
# Backend
cd backend
pip3 install -r requirements.txt

# Frontend
cd frontend
npm install
```

### Fix Stockfish Link
```bash
cd backend
rm stockfish
ln -sf $(which stockfish) ./stockfish
chmod +x stockfish
```

### Check Environment Files
```bash
# Backend
cat backend/.env

# Frontend
cat frontend/.env.local
```

---

## 🔑 API KEY SETUP

### Add OpenAI Key to Backend
```bash
echo "OPENAI_API_KEY=sk-your-key-here" > backend/.env
```

### Add OpenAI Key to Frontend
```bash
cat > frontend/.env.local << 'EOF'
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
EOF
```

---

## 🧹 CLEANUP

### Clear Frontend Cache
```bash
cd frontend
rm -rf .next node_modules
npm install
```

### Clear Backend Cache
```bash
cd backend
find . -type d -name "__pycache__" -exec rm -rf {} +
```

---

## 📦 PACKAGE MANAGEMENT

### Update Backend Packages
```bash
cd backend
pip3 install --upgrade -r requirements.txt
```

### Update Frontend Packages
```bash
cd frontend
npm update
```

---

## 🔍 DEBUGGING

### Check Backend Logs
```bash
tail -f backend/logs/*.log
```

### Check Frontend Logs
Look in the terminal where `./start_frontend.sh` is running.

### Test Backend API
```bash
# Health check
curl http://localhost:8000/meta

# Analyze position
curl "http://localhost:8000/analyze_position?fen=rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR%20w%20KQkq%20-%200%201"
```

### Test Frontend
```bash
# Check if it's running
curl http://localhost:3000
```

---

## 🐛 COMMON ISSUES

### "command not found: brew"
```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### "command not found: node"
```bash
brew link node@20
export PATH="/opt/homebrew/bin:$PATH"
```

### "Stockfish not found"
```bash
brew install stockfish
cd backend
ln -sf $(which stockfish) ./stockfish
```

### "Port already in use"
```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### "Cannot connect to backend"
- Make sure backend is running: `./status.sh`
- Check backend logs for errors
- Verify it's on port 8000: `lsof -i:8000`

---

## 📁 IMPORTANT FILE LOCATIONS

```
Chess-GPT/
├── backend/
│   ├── main.py              # Backend entry point
│   ├── requirements.txt     # Python dependencies
│   ├── .env                 # API keys (create this!)
│   ├── stockfish            # Chess engine binary
│   └── tactics.json         # Puzzle database
├── frontend/
│   ├── app/page.tsx         # Main frontend app
│   ├── package.json         # Node.js dependencies
│   └── .env.local           # Frontend config (create this!)
├── start.sh                 # Start both services ⭐
├── install_commands.sh      # Installation script ⭐
└── START_HERE.md            # Setup guide ⭐
```

---

## 🎯 QUICK START WORKFLOW

```bash
# 1. First time setup
./install_commands.sh

# 2. Start the app
./start.sh

# 3. Open browser
# http://localhost:3000

# 4. Stop the app
# Press Ctrl+C

# 5. Start again later
./start.sh
```

---

## 📖 DOCUMENTATION

- `START_HERE.md` - Read this first!
- `SETUP_SUMMARY.md` - What was done for you
- `INSTALL_STEPS.md` - Manual installation steps
- `NEW_COMPUTER_SETUP.md` - Detailed setup guide
- `README.md` - Project overview
- `SETUP_INSTRUCTIONS.md` - Usage instructions

---

## 💡 PRO TIPS

1. **Use `./start.sh`** - Simplest way to run everything
2. **Keep terminal open** - Don't close while app is running
3. **Check `./status.sh`** - Quick health check
4. **Save your API key** - Store it securely
5. **Use Chrome DevTools** - F12 for frontend debugging

---

## 🆘 GET HELP

1. Check error message first
2. Look in documentation files
3. Check `NEW_COMPUTER_SETUP.md` troubleshooting section
4. Verify all dependencies installed
5. Make sure API key is configured

---

## ⚡ ONE-LINERS

```bash
# Full restart (if something is stuck)
lsof -ti:3000 | xargs kill -9; lsof -ti:8000 | xargs kill -9; ./start.sh

# Quick reinstall of dependencies
cd backend && pip3 install -r requirements.txt && cd ../frontend && npm install && cd ..

# Check everything is installed
python3 --version && node --version && brew --version && which stockfish

# View all running processes
ps aux | grep -E "(python|node|uvicorn|next)"
```

---

🎯 **Most Common Command:** `./start.sh`

♟️ **Happy Chess Playing!**

