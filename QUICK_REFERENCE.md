# Chess GPT - Quick Reference Card

## 🚀 Startup

```bash
./start.sh        # Start both services
./status.sh       # Check if running
```

**Access:** http://localhost:3000

---

## 💬 Chat Commands

| Input | Result |
|-------|--------|
| `hi` / `hello` | Context-aware greeting with suggestions |
| `e4` / `Nf3` | Play a chess move |
| `analyze` | Analyze current position |
| `what should I do?` | Get move suggestions |
| `thanks` | Polite response |

---

## 🎨 Visual Annotations Legend

### Arrows:
- 🟢 **Green** = Best move (#1)
- 🔵 **Blue** = 2nd best move
- 🟡 **Yellow** = 3rd best move
- 🔴 **Red** = Opponent threat

### Highlights:
- 🟢 **Green Square** = Active piece (many moves)
- 🟠 **Orange Square** = Inactive/trapped piece

---

## 📊 Button Features

Click **📊** next to AI responses to see:
- Detected mode
- Current FEN position
- Chess GPT structured analysis
- Raw Stockfish engine data

---

## 🎯 Modes

| Mode | Use For |
|------|---------|
| **PLAY** | Playing against engine |
| **ANALYZE** | Position evaluation |
| **TACTICS** | Solving puzzles |
| **DISCUSS** | Learning & questions |

*Mode auto-detects from your message!*

---

## 🔧 Main Buttons

| Button | Action |
|--------|--------|
| 📊 Analyze Position | Deep analysis + visual annotations |
| 🧩 Next Tactic | Load a chess puzzle |
| 🔄 Reset Board | Return to starting position |
| 📋 Copy PGN | Export game notation |

---

## 🧠 What Gets Analyzed

When you click "Analyze Position":

✅ Best 3 moves (with arrows)
✅ Opponent threats (red arrows)
✅ Active pieces (green highlights)
✅ Inactive pieces (orange highlights)
✅ Strengths & weaknesses
✅ Piece mobility comparison
✅ Pawn structure
✅ Tactical themes
✅ Strategic plan

---

## 💡 Example Workflows

### Playing a Game:
```
1. Type "hi" → Get started
2. Type "e4" → Make your move
3. Engine responds
4. Continue playing
```

### Getting Advice:
```
1. Click "Analyze Position"
2. See arrows showing best moves
3. Click 📊 to see details
4. Ask "why is this good?"
```

### Learning:
```
1. Set up interesting position
2. Click "Analyze Position"
3. Study visual annotations
4. Ask questions about the plan
```

---

## 🎨 Analysis Output Structure

```
Verdict: = (Equal position)

Key Themes:
1. Opening development
2. Center control
3. Pawn structure

Strengths:
1. Superior piece mobility
2. Active pieces: Qd1, Nf3

Weaknesses:
1. Inactive pieces: Ra1
2. Doubled pawns (1)

Threats:
• No immediate threats

Candidate Moves:
1. e4 - Central control
2. d4 - Claims center
3. Nf3 - Develops knight

Critical Line (e4):
1. e4 e5
2. Nf3 Nc6
3. Bb5

Plan: Complete development, 
castle for safety, control center.

Avoid: Leaving pieces undeveloped.
```

---

## 🤖 AI Capabilities

The AI can:
- ✅ Answer in natural language
- ✅ Detect your intent automatically
- ✅ Provide context-based suggestions
- ✅ Show visual annotations
- ✅ Explain chess concepts
- ✅ Adapt to board state

---

## 📍 Troubleshooting

**Problem:** "Backend not available"
**Solution:** Run `./start.sh`

**Problem:** Moves not working
**Solution:** Refresh page (Ctrl+R / Cmd+R)

**Problem:** No visual annotations
**Solution:** Click "Analyze Position" button

---

## 🏆 Pro Tips

1. **Use visual annotations** - Learn from colored arrows
2. **Click 📊 often** - See the engine's thinking
3. **Ask questions naturally** - "What's the plan here?"
4. **Try all modes** - Each teaches different skills
5. **Study the "Strengths" section** - Know your advantages

---

## 🎯 Quick Command Reference

```bash
# Start
./start.sh

# Status check
./status.sh

# Frontend only
./start_frontend.sh

# Backend only
./start_backend.sh
```

---

## 📚 Full Documentation

- `COMPLETE_FEATURE_SUMMARY.md` - Everything explained
- `AI_BOARD_CONTROL.md` - Visual annotations guide
- `API_PIPELINE_UPGRADE.md` - How AI works
- `GENERAL_CHAT_FEATURE.md` - Chat system details

---

## ✨ Remember

**Your Chess GPT:**
- 🎯 Auto-detects what you want to do
- 🎨 Shows you the best moves visually
- 💬 Chats naturally like a coach
- 📊 Always transparent with data
- 🧠 Analyzes deeply with Stockfish

**Just start with "hi" and explore!** 🚀
