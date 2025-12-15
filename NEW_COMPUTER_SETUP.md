# 🚀 New Computer Setup Guide for Chess-GPT

Welcome! This guide will help you set up your new computer to run Chess-GPT.

## Prerequisites

You mentioned you have:
- ✅ **Cursor** - Already installed
- ✅ **GitHub** - Already set up

## What You Need to Install

This project requires:
1. **Homebrew** - macOS package manager
2. **Python 3.11+** - For the FastAPI backend
3. **Node.js 18+** - For the Next.js frontend
4. **Stockfish** - Chess engine for analysis
5. **OpenAI API Key** - For AI-powered chess commentary

## 🎯 Quick Setup (Recommended)

I've created an automated setup script that will install everything for you:

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
./setup_new_computer.sh
```

This script will:
- ✅ Check and install Homebrew if needed
- ✅ Install Python 3.11
- ✅ Install Node.js 20
- ✅ Install Stockfish chess engine
- ✅ Install all Python backend dependencies
- ✅ Install all Node.js frontend dependencies
- ✅ Set up Stockfish in the backend folder
- ✅ Create configuration files for API keys
- ✅ Give you a summary of what was installed

**Estimated time:** 5-15 minutes (depending on internet speed)

## 📋 Manual Setup (Alternative)

If you prefer to install things manually or the script fails:

### Step 1: Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

After installation, if you're on Apple Silicon (M1/M2/M3), add to your shell profile:
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### Step 2: Install Python 3.11

```bash
brew install python@3.11
```

Verify installation:
```bash
python3 --version
```

### Step 3: Install Node.js 20

```bash
brew install node@20
brew link node@20
```

Verify installation:
```bash
node --version
npm --version
```

### Step 4: Install Stockfish

```bash
brew install stockfish
```

Verify installation:
```bash
stockfish
# Type 'quit' to exit
```

### Step 5: Install Python Dependencies

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
pip3 install -r requirements.txt
```

### Step 6: Install Node.js Dependencies

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
npm install
```

### Step 7: Link Stockfish to Backend

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
ln -s $(which stockfish) ./stockfish
chmod +x stockfish
```

### Step 8: Configure API Keys

Create `backend/.env`:
```bash
OPENAI_API_KEY=your-openai-api-key-here
```

Create `frontend/.env.local`:
```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
```

## 🔑 Getting an OpenAI API Key

If you don't have an OpenAI API key yet:

1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to API keys section
4. Create a new API key
5. Copy and paste it into the `.env` files

## 🚀 Running the Application

After setup is complete, start the application:

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
./start.sh
```

This will start both the backend and frontend servers.

**Access the application:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 🔍 Verify Installation

After running the setup script, verify everything is installed:

```bash
# Check Homebrew
brew --version

# Check Python
python3 --version

# Check Node.js
node --version
npm --version

# Check Stockfish
which stockfish

# Check if backend dependencies are installed
cd backend
pip3 list | grep -E "fastapi|uvicorn|python-chess"

# Check if frontend dependencies are installed
cd ../frontend
npm list --depth=0
```

## ⚠️ Troubleshooting

### Homebrew Installation Issues

If Homebrew installation fails:
1. Make sure you have Xcode Command Line Tools: `xcode-select --install`
2. Try the installation again

### Python Not Found

If `python3` command is not found after installation:
```bash
brew link python@3.11
```

### Node.js Not Found

If `node` command is not found:
```bash
brew link node@20
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
```

### Stockfish Not Working

If stockfish binary doesn't work in backend:
```bash
cd backend
rm stockfish
ln -s $(which stockfish) ./stockfish
chmod +x stockfish
./stockfish  # Test it
```

### Permission Denied

If you get permission errors when running scripts:
```bash
chmod +x setup_new_computer.sh
chmod +x start.sh
chmod +x start_backend.sh
chmod +x start_frontend.sh
```

### Port Already in Use

If ports 3000 or 8000 are already in use:
```bash
# Find and kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

## 📚 Additional Resources

- **Full README**: See `README.md` for project overview
- **Setup Instructions**: See `SETUP_INSTRUCTIONS.md` for detailed usage
- **Quick Reference**: See `QUICK_REFERENCE.md` for command cheatsheet

## 🎮 What's Next?

Once everything is installed and running:

1. Open http://localhost:3000 in your browser
2. Select a mode (PLAY, ANALYZE, TACTICS, or DISCUSS)
3. Start playing chess with AI assistance!

**Features to explore:**
- 🎮 **PLAY Mode** - Play against Stockfish engine
- 📊 **ANALYZE Mode** - Deep position analysis
- 🧩 **TACTICS Mode** - Solve chess puzzles
- 💬 **DISCUSS Mode** - Chat about chess strategies

## ✅ Setup Checklist

- [ ] Homebrew installed
- [ ] Python 3.11+ installed
- [ ] Node.js 18+ installed
- [ ] Stockfish installed
- [ ] Backend dependencies installed (`pip3 install -r requirements.txt`)
- [ ] Frontend dependencies installed (`npm install`)
- [ ] Stockfish linked in backend folder
- [ ] OpenAI API key added to `backend/.env`
- [ ] OpenAI API key added to `frontend/.env.local`
- [ ] Application starts successfully with `./start.sh`
- [ ] Can access frontend at http://localhost:3000
- [ ] Can access backend at http://localhost:8000

---

**Need help?** Check the troubleshooting section or review the error messages carefully. Most issues are related to:
1. Missing API keys
2. Incorrect paths
3. Ports already in use
4. Dependencies not installed

Happy chess playing! ♟️

