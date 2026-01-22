# 🗄️ Supabase Integration - Complete Setup Guide

## Overview

This guide will help you set up Supabase for Chess GPT, giving you:
- ✅ User authentication (Google OAuth, magic links, email/password)
- ✅ Cloud database (games, positions, training cards, chat history)
- ✅ Multi-device sync
- ✅ Data persistence
- ✅ Collections/folders for organization

## Step 1: Create Supabase Project

### 1.1 Sign Up for Supabase
```
1. Go to https://supabase.com
2. Click "Start your project"
3. Sign in with GitHub (recommended)
4. Click "New Project"
```

### 1.2 Create Project
```
Organization: Create new or select existing
Project name: chess-gpt
Database password: [Generate strong password - SAVE THIS]
Region: Choose closest to you
Pricing: Free tier is fine for development
```

### 1.3 Wait for Setup
```
Takes 2-3 minutes to provision database
☕ Grab coffee while it sets up
```

## Step 2: Run SQL Migrations

### 2.1 Open SQL Editor
```
In Supabase dashboard:
1. Click "SQL Editor" in left sidebar
2. Click "New query"
```

### 2.2 Run Migrations in Order

**Run these files one at a time in the SQL editor:**

**Migration 1:** `backend/supabase/migrations/001_auth_and_profiles.sql`
```
Copy entire file contents → Paste in SQL editor → Run
✅ Creates profiles table with RLS
```

**Migration 2:** `backend/supabase/migrations/002_collections.sql`
```
Copy → Paste → Run
✅ Creates collections table
```

**Migration 3:** `backend/supabase/migrations/003_games.sql`
```
Copy → Paste → Run
✅ Creates games table with full analysis storage
```

**Migration 4:** `backend/supabase/migrations/004_positions.sql`
```
Copy → Paste → Run
✅ Creates positions table with tags
```

**Migration 5:** `backend/supabase/migrations/005_chat.sql`
```
Copy → Paste → Run
✅ Creates chat sessions and messages
```

**Migration 6:** `backend/supabase/migrations/006_training.sql`
```
Copy → Paste → Run
✅ Creates training cards with SRS
```

**Migration 7:** `backend/supabase/migrations/007_rpcs.sql`
```
Copy → Paste → Run
✅ Creates stored procedures
```

### 2.3 Verify Tables Created
```
Click "Table Editor" in sidebar
Should see:
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

## Step 3: Configure Google OAuth (Optional but Recommended)

### 3.1 Get Google OAuth Credentials
```
1. Go to https://console.cloud.google.com
2. Create new project: "Chess GPT"
3. Enable "Google+ API"
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Application type: Web application
6. Authorized redirect URIs:
   https://[YOUR-PROJECT-REF].supabase.co/auth/v1/callback
7. Copy Client ID and Client Secret
```

### 3.2 Configure in Supabase
```
Supabase Dashboard:
1. Go to Authentication → Providers
2. Find "Google"
3. Toggle "Enable"
4. Paste Client ID
5. Paste Client Secret
6. Save
```

## Step 4: Get Supabase Credentials

### 4.1 Project URL and Keys
```
In Supabase Dashboard:
1. Click "Project Settings" (gear icon)
2. Click "API"
3. Copy these values:
   - Project URL
   - anon public key
   - service_role key (keep secret!)
```

## Step 5: Configure Environment Variables

### 5.1 Frontend (.env.local)
```bash
cd frontend
```

Create `.env.local`:
```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 5.2 Backend (.env)
```bash
cd backend
```

Add to existing `.env` file:
```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Existing variables
OPENAI_API_KEY=sk-...
STOCKFISH_PATH=./stockfish
```

⚠️ **NEVER commit .env files to git!**

## Step 6: Install Dependencies

### 6.1 Backend
```bash
cd backend
pip3 install -r requirements.txt
```

This installs:
- supabase==2.*
- All existing dependencies

### 6.2 Frontend
```bash
cd frontend
npm install
```

This installs:
- @supabase/supabase-js
- @supabase/auth-ui-react
- @supabase/auth-ui-shared

## Step 7: Test Connection

### 7.1 Test Backend
```bash
cd backend
python3 << 'EOF'
from supabase_client import SupabaseClient
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

client = SupabaseClient(url, key)
print("✅ Supabase connection successful!")
EOF
```

Expected output:
```
✅ Supabase client initialized: https://xxxxx.supabase.co
✅ Supabase connection successful!
```

### 7.2 Test Frontend
```bash
cd frontend
npm run dev
```

Visit http://localhost:3000
Should see auth modal on first load

## Step 8: Verify RLS Policies

### 8.1 Check RLS Enabled
```
In Supabase Dashboard:
1. Go to "Table Editor"
2. Select each table
3. Click "RLS" button
4. Verify "Enable RLS" is ON
5. See list of policies
```

### 8.2 Test Policies
```
1. Sign in through frontend
2. Try to save a game
3. Check "Table Editor" → games table
4. Should see your game with your user_id
5. Try accessing with different user_id (should fail)
```

## Step 9: Data Migration (Optional)

If you have existing cache data:

```bash
cd backend
python3 migrate_cache_to_supabase.py
```

This will:
- Read all JSONL cache files
- Convert to Supabase format
- Insert into tables
- Verify migration

## Troubleshooting

### Issue: "Missing Supabase environment variables"
**Fix:**
- Check .env.local and .env files exist
- Verify variable names match exactly
- Restart dev servers after adding variables

### Issue: "Row Level Security policy violation"
**Fix:**
- Run all 7 migrations in order
- Check RLS is enabled on all tables
- Verify policies exist in Table Editor

### Issue: "Google OAuth not working"
**Fix:**
- Check redirect URI matches exactly
- Verify Google credentials in Supabase
- Check Google Cloud Console project is active

### Issue: "Auth stuck / can’t sign in after recent changes"
**Fix (local dev):**
- Clear old Supabase auth keys in Local Storage for `http://localhost:3000`:
  - `sb-<project-ref>-auth-token`
  - `sb-<project-ref>-auth-token-code-verifier`
- Restart the frontend dev server after changing `.env.local` or auth settings.

### Issue: "Database connection failed"
**Fix:**
- Verify SUPABASE_URL is correct
- Check service_role key (not anon key) in backend
- Verify network connection

## What Each Migration Does

| File | Creates | Purpose |
|------|---------|---------|
| 001 | profiles | User profiles with chess platform usernames |
| 002 | collections | Folders for organizing content |
| 003 | games | Game storage with full analysis |
| 004 | positions | Saved positions with tags |
| 005 | chat | Chat history persistence |
| 006 | training | Drill cards with SRS |
| 007 | RPCs | Stored procedures for atomic operations |

## Environment Variable Reference

### Frontend (.env.local)
```
NEXT_PUBLIC_SUPABASE_URL=        # Your project URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=   # Public anon key (safe for client)
```

### Backend (.env)
```
SUPABASE_URL=                    # Same as frontend
SUPABASE_SERVICE_ROLE_KEY=       # Secret! Server-side only
OPENAI_API_KEY=                  # Existing
STOCKFISH_PATH=                  # Existing
```

## Security Checklist

- [ ] Service role key only in backend .env (never frontend!)
- [ ] .env files in .gitignore
- [ ] RLS enabled on all tables
- [ ] Auth policies tested
- [ ] Google OAuth redirect URIs configured
- [ ] Database password saved securely

## Next Steps After Setup

1. ✅ Restart backend: `cd backend && python3 main.py`
2. ✅ Restart frontend: `cd frontend && npm run dev`
3. ✅ Visit http://localhost:3000
4. ✅ See auth modal
5. ✅ Sign in with Google
6. ✅ Start using Chess GPT with persistence!

## Benefits You Get

✅ **User Accounts** - Each user has their own data
✅ **Cloud Storage** - Access from any device
✅ **Collections** - Organize games and positions
✅ **Chat History** - Conversations persist
✅ **Training Progress** - SRS state synced
✅ **Analytics** - Query across all your data
✅ **Secure** - Row-level security
✅ **Scalable** - Postgres performance

---

**Setup Time:** 15-20 minutes  
**Difficulty:** Medium (mostly copy-paste)  
**Result:** Production-ready database!

🚀 Follow these steps and you'll have Supabase fully integrated!

