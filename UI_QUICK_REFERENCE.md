# UI Quick Reference

## ChatGPT-Style Interface - At a Glance

### Initial Screen
```
- Large centered input box (hero composer)
- Rotating example prompts above
- "Show chessboard" chip on input
- "Load game" link below
- Clean, monochrome design
```

### After First Message
```
- Conversation stream appears
- Input moves to bottom (sticky)
- Board dock optional (toggle with chip or 'B' key)
- All features via chat
```

### Keyboard Shortcuts
- `Cmd/Ctrl+K` - Focus input
- `B` - Toggle board
- `Cmd/Ctrl+L` - Load game
- `Esc` - Close modals
- `Enter` - Send message
- `Shift+Enter` - New line

### Theme Toggle
- Day/Night switch in top bar
- Monochrome UI (only board has color)
- Persists per user (when auth added)

### Features (Chat-Driven)
- **Position analysis:** "who's winning?"
- **Move analysis:** "was e4 good?"
- **Game review:** "review my last 5 games"
- **Training:** "create training on tactics"
- **Lessons:** "teach me the Sicilian"
- **Load game:** Use Load Game panel or paste PGN

### Raw Data Access
- Every assistant message has "Raw Data" button (top-right)
- Expands inline JSON panel
- Shows full analysis, themes, tags, tool calls
- Copy button included

### Board Dock
- Slides down above bottom composer
- Interactive - make moves by clicking
- Shows FEN
- Displays smart annotations (only what LLM mentions)

### Load Game Panel
- Three tabs: PGN, FEN, Link
- Inline validation
- Preview before loading
- "Use in chat" button

### History Curtain
- Left drawer (slide from left)
- Search conversations
- Chronological list
- Click to load thread
- Ready for Supabase integration

---

## Color Scheme

### Day Theme
- Background: White (#ffffff)
- Text: Black (#1a1a1a)
- Borders: Light grey (#e0e0e0)

### Night Theme
- Background: Near-black (#1a1a1a)
- Text: Off-white (#f5f5f5)
- Borders: Dark grey (#404040)

### Board Annotations (Only Colored Element)
- Green: Suggestions, control (semi-transparent)
- Red: Threats, targets
- Amber: Warnings
- Gold: Tactics, special

---

## Feature Access

### All Features Work via Chat:

**Example queries:**
```
"who's winning here?"
→ Uses cached analysis, instant response

"was Nf3 good?"
→ Shows move quality from cache

"review this game [paste PGN]"
→ LLM calls review_full_game tool

"create training on my endgame mistakes"
→ LLM calls training tools

"teach me the Italian Game"
→ LLM calls lesson tool

"should I play Bc4?"
→ LLM uses candidate moves from cache
```

**No buttons needed** - everything is natural language!

---

## Technical Details

### State Management
- Board state: FEN, PGN, arrows, highlights, dock status
- Chat state: Messages, thread ID, first message flag
- Analysis cache: Auto-populated after moves
- UI state: History, load panel, theme

### Message Flow
1. User types message
2. If first message → layout transitions
3. Message sent to LLM via backend
4. LLM uses cached analysis or calls tools
5. Response filtered for emoji
6. Message added with Raw Data button
7. Smart annotations applied to board

### Analysis Pipeline
- Auto-runs after every move (4-6 seconds)
- Position analysis (Stockfish + themes + tags)
- Move analysis (quality, theory check, alternatives)
- Cached by FEN for instant LLM access
- Input disabled during analysis

---

## Files Structure

```
frontend/
├── app/
│   ├── page.tsx (rebuilt, 5222 lines, all logic preserved)
│   └── styles.css (original, augmented)
├── components/
│   ├── TopBar.tsx (new)
│   ├── HeroComposer.tsx (new)
│   ├── BottomComposer.tsx (new)
│   ├── Conversation.tsx (new)
│   ├── MessageBubble.tsx (new)
│   ├── BoardDock.tsx (new)
│   ├── HistoryCurtain.tsx (new)
│   ├── LoadGamePanel.tsx (new)
│   ├── RotatingExamples.tsx (new)
│   ├── Board.tsx (original, unchanged)
│   └── ... (other original components)
├── utils/
│   ├── emojiFilter.ts (new)
│   └── animations.ts (new)
├── styles/
│   └── chatUI.css (new, 400+ lines)
└── lib/ (all original, unchanged)
```

---

## What's Preserved

### All Backend
- Auto-analysis system
- LLM tool calling
- Theme-based analysis
- Move quality evaluation
- Opening theory detection
- Smart annotation filtering
- All endpoints working

### All Chess Logic
- Move handling
- Game state management
- Analysis caching
- Annotation generation
- PGN/FEN parsing
- Tool execution

### All Features
- Position analysis
- Move analysis
- Game review
- Personal review (Chess.com/Lichess fetch)
- Training generation
- Lesson system
- Drill SRS system

**Nothing broken, everything enhanced!**

---

## Deployment

1. Frontend automatically rebuilds (Next.js dev server)
2. No backend changes needed
3. All APIs compatible
4. Zero breaking changes

**Ready to use immediately!**

Type a message and experience the new ChatGPT-style Chess GPT interface!

