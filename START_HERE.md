# 🚀 START HERE - New Computer Setup

## What You Need to Do

Since you only have Cursor and GitHub set up, you need to install the Chess-GPT dependencies.

## 🎯 EASIEST METHOD: Run the Install Script

Open Terminal and run:

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
./install_commands.sh
```

This script will:
1. ✅ Install Xcode Command Line Tools (popup will appear)
2. ✅ Install Homebrew package manager
3. ✅ Install Node.js 20 (for frontend)
4. ✅ Install Stockfish chess engine
5. ✅ Install all Python packages
6. ✅ Install all Node.js packages
7. ✅ Set up configuration files
8. ✅ Prompt you for your OpenAI API key

**Total time: ~20-30 minutes**

---

## Current Status

I've already checked your system:

| Software | Status |
|----------|--------|
| Python 3 | ✅ Installed (system version) |
| Xcode Tools | ❌ Not installed |
| Homebrew | ❌ Not installed |
| Node.js | ❌ Not installed |
| Stockfish | ❌ Not installed |

---

## After Installation

Once the script finishes, start the app:

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
./start.sh
```

Then open: **http://localhost:3000**

---

## 🔑 OpenAI API Key

You'll need an OpenAI API key for the AI features:

1. Go to https://platform.openai.com/api-keys
2. Sign in or create account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)
5. Enter it when the install script asks

**Don't have one yet?** You can skip it during installation and add it later.

---

## Manual Installation (Alternative)

If you prefer step-by-step manual installation, see **`INSTALL_STEPS.md`**

---

## Files I Created for You

- ✅ `install_commands.sh` - Automated installation script (RUN THIS!)
- ✅ `INSTALL_STEPS.md` - Manual step-by-step instructions
- ✅ `NEW_COMPUTER_SETUP.md` - Detailed setup documentation
- ✅ `setup_new_computer.sh` - Alternative auto-install script

---

## Quick Commands Reference

**Install everything:**
```bash
./install_commands.sh
```

**Start the app:**
```bash
./start.sh
```

**Check if services are running:**
```bash
./status.sh
```

**View logs:**
```bash
./watch_backend_logs.sh
```

---

## What This Project Is

Chess-GPT is a chess application that combines:
- 🎮 **Play Mode** - Play against Stockfish AI
- 📊 **Analyze Mode** - Deep chess position analysis
- 🧩 **Tactics Mode** - Solve chess puzzles
- 💬 **Discuss Mode** - Chat about chess with AI

**Tech Stack:**
- Backend: Python + FastAPI + Stockfish
- Frontend: Next.js + React + TypeScript
- AI: OpenAI GPT-4

---

## Troubleshooting

### Script fails at Xcode installation
- A popup should appear to install Xcode
- Click "Install" and wait (5-10 minutes)
- If no popup, run manually: `xcode-select --install`

### "brew: command not found"
- Close and reopen Terminal after Homebrew installation
- Or run: `eval "$(/opt/homebrew/bin/brew shellenv)"`

### "Permission denied"
- Run: `chmod +x install_commands.sh`
- Then try again: `./install_commands.sh`

### Other issues
- See `NEW_COMPUTER_SETUP.md` for detailed troubleshooting
- Check `INSTALL_STEPS.md` for manual installation

---

## Need Help?

1. Read `NEW_COMPUTER_SETUP.md` - Comprehensive setup guide
2. Read `INSTALL_STEPS.md` - Step-by-step manual instructions
3. Read `README.md` - Project overview and features
4. Read `SETUP_INSTRUCTIONS.md` - Usage instructions

---

## After Setup is Complete

See `QUICK_REFERENCE.md` for common commands and usage tips.

---

🎯 **Ready? Run this now:**

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
./install_commands.sh
```

Good luck! ♟️

