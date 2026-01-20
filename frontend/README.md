# Chess GPT Frontend

Next.js frontend for Chess GPT with react-chessboard and OpenAI integration.

## Prerequisites

- Node.js 18+
- npm or yarn

## Installation

1. Install dependencies:
```bash
npm install
```

2. Create environment configuration:
```bash
cp .env.local.example .env.local
```

3. Edit `.env.local` and add your OpenAI API key:
```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8001
NEXT_PUBLIC_OPENAI_API_KEY=sk-your-actual-openai-key
OPENAI_MODEL=gpt-4o-mini
```

## Running the Application

Start the development server:
```bash
npm run dev
```

The app will be available at `http://localhost:3000`

## Dev Routes

Use these dev-only pages to compare analytics overview UIs:

- `http://localhost:3000/dev/analytics-overview-v1`
- `http://localhost:3000/dev/analytics-overview-v2`

## Features

### Modes

**PLAY** - Play against the engine
- Make moves on the board by dragging pieces
- Engine responds automatically
- Adjust engine strength (ELO rating)
- View evaluation after each move

**ANALYZE** - Deep position analysis
- Click "Analyze Position" to get:
  - Centipawn evaluation
  - Win probability
  - Top candidate moves with variations
  - Tactical threats
  - Piece quality assessment
  - Positional themes
- Optional LLM commentary for natural language explanations

**TACTICS** - Solve chess puzzles
- Click "Next Tactic" to load a puzzle
- Try to find the winning move/sequence
- Click "Reveal Solution" if stuck
- Puzzles are rated from 1200-2200

**DISCUSS** - Chat about chess
- Ask questions about positions, plans, strategies
- Discuss chess principles and ideas
- Get explanations without concrete analysis

### Board Features

- Drag and drop pieces to make moves
- Visual arrows and square highlights for annotations
- Automatic move validation
- PGN export
- Board flip for tactics

### Chat Features

- Real-time conversation with Chess GPT
- Mode-aware routing (auto-detects intent)
- Toggle LLM on/off (show only structured engine data)
- Context-aware responses (includes FEN, PGN, annotations)

### Load Game Panel

- PGN/FEN import, cloud game lookup, and **Photo** tab.
- Photo tab accepts drag & drop uploads or camera capture, sends the image to the backend vision endpoint, and renders the detected FEN on a mini board.
- Digital preset is optimised for Chess GPT screenshots; physical boards are supported via GPT-4o-mini vision with uncertainty highlights so you can manually tweak squares before loading.

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx        # Root layout with styles
│   ├── page.tsx          # Main application page
│   └── styles.css        # Global CSS
├── components/
│   ├── Board.tsx         # Chess board component
│   ├── Chat.tsx          # Chat interface
│   ├── ModeChip.tsx      # Mode selector dropdown
│   └── RouterHint.tsx    # Mode routing indicator
├── lib/
│   └── api.ts           # Backend API client
├── types/
│   └── index.ts         # TypeScript types
├── package.json
├── tsconfig.json
└── next.config.js
```

## Environment Variables

- `NEXT_PUBLIC_BACKEND_URL` - Backend API URL (default: http://localhost:8001)
- `NEXT_PUBLIC_OPENAI_API_KEY` - Your OpenAI API key
- `OPENAI_MODEL` - OpenAI model to use (default: gpt-4o-mini)

⚠️ **Note:** For local development, the API key is exposed client-side. This is acceptable for local use but should never be done in production. For production, implement a backend proxy for OpenAI calls.

## Building for Production

```bash
npm run build
npm run start
```

## Troubleshooting

**Backend not available:**
- Ensure backend is running on http://localhost:8001
- Check NEXT_PUBLIC_BACKEND_URL in .env.local

**Board not loading:**
- Check browser console for errors
- Ensure all dependencies installed: `npm install`

**LLM errors:**
- Verify NEXT_PUBLIC_OPENAI_API_KEY is set correctly
- Check API key has sufficient credits
- Try toggling LLM off to use structured output only

**Moves not registering:**
- Ensure move is legal in current position
- Check if waiting for engine response
- Try resetting the board

## Development Tips

- Use browser DevTools to inspect state
- Check Network tab for API calls
- Toggle LLM off to test backend-only functionality
- Use "Copy PGN" to save games for analysis

