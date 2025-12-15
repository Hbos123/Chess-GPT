# 🚀 Supabase One-Click Setup

## Complete Schema in One Script!

I've combined all 7 SQL migrations into **one file** you can run in a single go.

## Quick Setup (10 Minutes)

### Step 1: Create Supabase Project (3 min)
```
1. Go to https://supabase.com
2. Sign in (GitHub recommended)
3. Click "New Project"
4. Fill in:
   - Name: chess-gpt
   - Database Password: [Generate & save]
   - Region: [Choose closest]
5. Click "Create new project"
6. Wait ~2 minutes for provisioning
```

### Step 2: Run Complete Schema (2 min)
```
1. In Supabase Dashboard → Click "SQL Editor"
2. Click "New query"
3. Open: backend/supabase/migrations/000_complete_schema.sql
4. Copy ENTIRE file (Cmd+A, Cmd+C)
5. Paste into SQL Editor (Cmd+V)
6. Click "Run" or press Cmd+Enter
7. Wait ~10 seconds
8. See success message:
   ✅ Chess GPT Supabase schema setup complete!
```

### Step 3: Verify Tables (1 min)
```
Click "Table Editor" in sidebar
Should see 11 tables:
✅ profiles
✅ collections
✅ games
✅ positions
✅ chat_sessions
✅ chat_messages
✅ training_cards
✅ training_sessions
✅ training_attempts
✅ collection_games
✅ collection_positions
```

### Step 4: Get Credentials (2 min)
```
1. Click "Project Settings" (gear icon)
2. Click "API" in sidebar
3. Copy these THREE values:

   Project URL:
   https://xxxxxxxxxxxxx.supabase.co
   
   anon public (safe for client):
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   
   service_role (SECRET - server only):
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Step 5: Configure Environment (2 min)

**Frontend - Create `frontend/.env.local`:**
```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Backend - Add to `backend/.env`:**
```env
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Keep existing:
OPENAI_API_KEY=sk-...
STOCKFISH_PATH=./stockfish
```

### Step 6: Install Dependencies (2 min)

**Backend:**
```bash
cd backend
pip3 install supabase
```

**Frontend:**
```bash
cd frontend
npm install
```

This installs:
- @supabase/supabase-js
- @supabase/auth-ui-react
- @supabase/auth-ui-shared

### Step 7: Test (1 min)

**Backend:**
```bash
cd backend
python3 << 'EOF'
from supabase_client import SupabaseClient
import os
from dotenv import load_dotenv

load_dotenv()
client = SupabaseClient(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)
print("✅ Backend → Supabase connection working!")
EOF
```

**Expected:**
```
✅ Supabase client initialized: https://xxxxx.supabase.co
✅ Backend → Supabase connection working!
```

## What Just Got Created

Running that ONE SQL script created:

### Tables (11):
- profiles
- collections
- games (with game_review jsonb)
- positions (with tags array)
- chat_sessions
- chat_messages
- training_cards (with SRS state)
- training_sessions
- training_attempts
- collection_games
- collection_positions

### Indexes (30+):
- Fast queries by user_id
- Fast date/time lookups
- GIN indexes for JSONB/arrays
- Compound indexes for filtering

### RLS Policies (25+):
- Row-level security on ALL tables
- Users can only access their own data
- Automatic with auth.uid()

### Stored Procedures (5):
- save_game_review() - Atomic game save
- save_position() - Position save
- get_user_stats() - Performance metrics
- get_srs_due_cards() - Training queue
- update_card_srs() - SRS algorithm

### Triggers (4):
- Auto-update timestamps
- Auto-create profile on signup
- Update chat session metadata

## What You Can Do Now

### Without Code Changes:
```
✅ Database ready
✅ Auth system configured
✅ RLS security active
✅ Ready to store data
```

### After Wiring Up (Next Phase):
```
✅ User sign in/signup
✅ Save analyzed games
✅ Cloud training cards
✅ Persistent chat history
✅ Multi-device sync
```

## Optional: Configure Google OAuth (5 min)

### Get Google Credentials:
```
1. https://console.cloud.google.com
2. Create project "Chess GPT"
3. APIs & Services → Credentials
4. Create OAuth 2.0 Client ID
5. Type: Web application
6. Redirect URI: https://[YOUR-PROJECT].supabase.co/auth/v1/callback
7. Copy Client ID and Secret
```

### Add to Supabase:
```
1. Supabase → Authentication → Providers
2. Find "Google"
3. Enable
4. Paste Client ID
5. Paste Client Secret  
6. Save
```

## Next Steps

### Immediate:
```
✅ Supabase configured
✅ Schema created
✅ Credentials saved
✅ Dependencies will install when needed
```

### Integration Work (1-2 hours):
```
1. Wire Auth into frontend (layout.tsx, page.tsx)
2. Update endpoints to use Supabase
3. Test auth flow
4. Test data persistence
5. Deploy!
```

## Files You Just Set Up

**Single SQL Script:**
- `000_complete_schema.sql` (600+ lines)
  - Replaces running 7 separate files
  - Creates everything in one go
  - Includes verification at end

**Already Created (Ready to Use):**
- `backend/supabase_client.py` - Python wrapper
- `frontend/lib/supabase.ts` - JS client
- `frontend/contexts/AuthContext.tsx` - Auth state
- `frontend/components/AuthModal.tsx` - Login UI

## Verification Checklist

After running the script:

- [ ] See success message in SQL editor
- [ ] Table Editor shows 11 tables
- [ ] Each table has RLS enabled (lock icon)
- [ ] Project Settings → API shows keys
- [ ] Environment variables set
- [ ] Dependencies installed

## Troubleshooting

**If script fails:**
- Check you're in a fresh project
- Try running again (some CREATE IF NOT EXISTS)
- Check error message for line number
- Verify moddatetime extension enabled

**If tables missing:**
- Refresh Table Editor
- Check SQL output for errors
- Verify script ran completely

**If RLS not working:**
- Click table → RLS button → Should see "Enabled"
- Check policies exist in table view
- Test with authenticated user

---

## ✅ Summary

**Setup time:** 10 minutes
**SQL lines:** 600+ (all in one file!)
**Tables created:** 11
**Policies created:** 25+
**RPCs created:** 5

**Result:** Production-ready Supabase database!

🗄️ **ONE SCRIPT, COMPLETE SETUP!** 🚀

