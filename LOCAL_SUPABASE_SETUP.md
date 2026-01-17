# 🏠 Local Supabase Setup Guide

This guide shows you how to run Chess-GPT with a local PostgreSQL database instead of remote Supabase. All data persists in `./data/supabase_local/`.

## ✅ What's Set Up

- ✅ Local PostgreSQL database running on port 5433
- ✅ All migrations applied
- ✅ Data persists in `./data/supabase_local/`
- ✅ Backend adapter for local PostgreSQL
- ✅ Scripts to start/stop the database

## 🚀 Quick Start

### 1. Start Local Database

```bash
./setup_local_supabase.sh
```

This will:
- Initialize PostgreSQL in `./data/supabase_local/`
- Start PostgreSQL on port 5433
- Create database `chess_gpt_local`
- Run all migrations

### 2. Configure Environment

```bash
./configure_local_supabase.sh
```

This updates `backend/.env` to use local PostgreSQL.

### 3. Start Backend

```bash
cd backend
python3 main.py
```

The backend will automatically detect and use local PostgreSQL.

## 📁 Data Persistence

All data is stored in:
```
./data/supabase_local/
```

This folder contains:
- PostgreSQL data files
- Database logs
- Process ID file

**To backup:** Copy the entire `data/supabase_local/` folder.

**To reset:** Stop database, delete folder, run setup again.

## 🛑 Stop Database

```bash
./stop_local_supabase.sh
```

Or manually:
```bash
kill $(cat data/supabase_local/postgres.pid)
```

## 🔄 Restart Database

```bash
./stop_local_supabase.sh
./setup_local_supabase.sh
```

## 📊 Connection Info

- **Host:** localhost
- **Port:** 5433
- **Database:** chess_gpt_local
- **User:** postgres
- **Connection String:** `postgresql://postgres@localhost:5433/chess_gpt_local`

## 🔧 Manual Database Access

```bash
# Connect with psql
psql postgresql://postgres@localhost:5433/chess_gpt_local

# Or with explicit host/port
psql -h localhost -p 5433 -U postgres -d chess_gpt_local
```

## 🔀 Switching Between Local and Remote

### Use Local (Current Setup)
```bash
# backend/.env should have:
LOCAL_POSTGRES_URL=postgresql://postgres@localhost:5433/chess_gpt_local
```

### Use Remote Supabase
```bash
# Comment out LOCAL_POSTGRES_URL and uncomment:
# SUPABASE_URL=https://cbskaefmgmcyhrblsgez.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=...
```

The backend automatically detects which one to use.

## 🐛 Troubleshooting

### Database won't start
```bash
# Check if port 5433 is in use
lsof -i :5433

# Kill existing process
kill $(lsof -ti:5433)

# Try setup again
./setup_local_supabase.sh
```

### Migrations failed
```bash
# Check database logs
cat data/supabase_local/postgres.log

# Re-run migrations
./run_local_migrations.sh
```

### Connection refused
```bash
# Verify database is running
pg_isready -h localhost -p 5433

# If not, start it
./setup_local_supabase.sh
```

## 📝 Notes

- **Frontend Auth:** Frontend can still use remote Supabase for authentication. Only backend data storage uses local PostgreSQL.
- **No Docker Required:** This setup uses direct PostgreSQL, no Docker needed.
- **Port 5433:** Uses port 5433 to avoid conflicts with system PostgreSQL (usually on 5432).
- **Data Persistence:** Data survives restarts. Only deleted if you remove `data/supabase_local/`.

## 🎯 What Works

✅ Game storage and retrieval  
✅ Profile management  
✅ Analytics RPC functions  
✅ All database operations  

## ⚠️ Limitations

- Frontend auth still uses remote Supabase (can be changed if needed)
- Some advanced Supabase features not available (but core functionality works)
- Manual backup required (just copy the data folder)

## 🔄 Migrating Back to Remote

When your network issues are resolved:

1. Stop local database: `./stop_local_supabase.sh`
2. Update `backend/.env`: Comment out `LOCAL_POSTGRES_URL`, uncomment `SUPABASE_URL`
3. Restart backend

Your remote Supabase database will be used again.

