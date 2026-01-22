# 🚀 Step-by-Step Installation for Brand New Mac

Since this is a fresh computer, follow these steps **in order**:

## Step 1: Install Xcode Command Line Tools (REQUIRED FIRST!)

This provides essential developer tools for macOS.

```bash
xcode-select --install
```

**A popup window will appear.** Click "Install" and wait for it to complete (5-10 minutes).

After installation completes, verify:
```bash
xcode-select -p
```

You should see: `/Library/Developer/CommandLineTools`

---

## Step 2: Install Homebrew

Homebrew is the package manager we'll use to install everything else.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**Important:** After installation, Homebrew will show you commands to run. They look like:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

**Run those commands!** Then verify Homebrew works:

```bash
brew --version
```

---

## Step 3: Install Python 3

```bash
brew install python@3.11
```

Verify:
```bash
python3 --version
```

---

## Step 4: Install Node.js

```bash
brew install node@20
```

Verify:
```bash
node --version
npm --version
```

---

## Step 5: Install Stockfish Chess Engine

```bash
brew install stockfish
```

Verify:
```bash
stockfish
```
(Type `quit` to exit)

---

## Step 6: Install Python Dependencies for Backend

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
pip3 install -r requirements.txt
```

---

## Step 7: Install Node.js Dependencies for Frontend

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
npm install
```

---

## Step 8: Link Stockfish to Backend

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
ln -s $(which stockfish) ./stockfish
chmod +x stockfish
```

---

## Step 9: Configure OpenAI API Key

### Get an API Key:
1. Go to https://platform.openai.com/api-keys
2. Sign in or create account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)

### Add to Backend:
```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
cat > .env << 'EOF'
OPENAI_API_KEY=sk-your-actual-key-here
EOF
```

Replace `sk-your-actual-key-here` with your actual key!

### Add to Frontend:
```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
cat > .env.local << 'EOF'
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_OPENAI_API_KEY=sk-your-actual-key-here
OPENAI_MODEL=gpt-4o-mini
EOF
```

Again, replace `sk-your-actual-key-here` with your actual key!

---

## Step 10: Start the Application! 🎉

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
./start.sh
```

Open your browser to:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs

---

## Quick Commands Summary

**After initial setup, to start the app:**
```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
./start.sh
```

**To check if services are running:**
```bash
./status.sh
```

**To stop services:**
```bash
# Press Ctrl+C in the terminal where they're running
```

---

## Troubleshooting

### "xcode-select: command not found"
- You need to install Xcode Command Line Tools first (Step 1)

### "brew: command not found" 
- Run the initialization commands Homebrew showed after installation
- Close and reopen your terminal

### "python3: command not found"
- Make sure Homebrew is working first: `brew --version`
- Try: `brew link python@3.11`

### "node: command not found"
- Make sure Homebrew is working first: `brew --version`
- Try: `brew link node@20`
- Add to PATH: `export PATH="/opt/homebrew/bin:$PATH"`

### "Cannot connect to backend"
- Make sure backend is running on port 8000
- Check backend logs for errors
- Verify Stockfish binary exists: `ls -la backend/stockfish`

### "OpenAI API error"
- Verify your API key is correct
- Make sure you have credits in your OpenAI account
- Check the key starts with `sk-`

---

## Installation Time Estimate

- Step 1 (Xcode): 5-10 minutes
- Step 2 (Homebrew): 2-5 minutes
- Step 3-5 (Python, Node, Stockfish): 5-10 minutes
- Step 6-7 (Dependencies): 2-5 minutes
- Step 8-9 (Configuration): 2-3 minutes

**Total: ~20-35 minutes**

---

## What Gets Installed

### System Software:
- **Xcode Command Line Tools** (~1.5 GB)
- **Homebrew** (~50 MB)
- **Python 3.11** (~100 MB)
- **Node.js 20** (~150 MB)
- **Stockfish** (~2 MB)

### Python Packages (backend):
- fastapi (web framework)
- uvicorn (ASGI server)
- python-chess (chess logic)
- pydantic (data validation)
- python-dotenv (environment variables)
- openai (API client)

### Node.js Packages (frontend):
- react & react-dom (UI framework)
- next (React framework)
- react-chessboard (chess board component)
- chess.js (chess logic)
- openai (API client)
- typescript (type checking)
- zod (validation)

**Total disk space needed: ~2-3 GB**

---

🎯 **Start with Step 1 and work through sequentially!**

