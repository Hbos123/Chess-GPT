# 🔍 Supabase Connection Diagnosis

## ✅ What We Found

### Project Status
- ✅ **Project exists**: `cbskaefmgmcyhrblsgez` (linked in CLI)
- ✅ **Region**: North EU (Stockholm)
- ✅ **HTTPS API works**: `https://cbskaefmgmcyhrblsgez.supabase.co` responds
- ✅ **General connectivity**: `supabase.com` resolves fine

### ❌ The Problem: DNS Resolution Failure

**Root Cause**: The `db.` subdomain is not resolving
```
❌ db.cbskaefmgmcyhrblsgez.supabase.co → DNS lookup fails
❌ Port 5432 test → DNS error (can't resolve hostname)
❌ Port 6543 (pooler) test → DNS error (can't resolve hostname)
```

This is **NOT** a SQL issue, credentials issue, or port blocking issue. It's a **DNS resolution problem**.

## 🔧 Solutions (Try in Order)

### 1️⃣ **Use Transaction Pooler** (Recommended First Try)

The pooler uses a different hostname that may resolve better:

**Connection String Format:**
```
postgresql://postgres.<PROJECT_REF>:<PASSWORD>@<PROJECT_REF>.pooler.supabase.com:6543/postgres
```

**For your project:**
```
postgresql://postgres.cbskaefmgmcyhrblsgez:<PASSWORD>@cbskaefmgmcyhrblsgez.pooler.supabase.com:6543/postgres
```

**Get your password:**
- Supabase Dashboard → Settings → Database → Database Password
- Or reset it if you don't have it

**Test the pooler:**
```bash
# Test if pooler hostname resolves
ping cbskaefmgmcyhrblsgez.pooler.supabase.com

# Test port connectivity
nc -vz cbskaefmgmcyhrblsgez.pooler.supabase.com 6543
```

### 2️⃣ **Run the Migration Script**

I've created a script that tries pooler first, then direct connection:

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
python3 scripts/run_migrations_direct.py
```

The script will:
- ✅ Load environment from `.env` automatically
- ✅ Try transaction pooler first (port 6543)
- ✅ Fall back to direct connection (port 5432)
- ✅ Show detailed error messages
- ✅ Prompt for database password if not in `.env`

**Add password to `.env` (optional):**
```bash
echo "SUPABASE_DB_PASSWORD=your_password_here" >> backend/.env
```

### 3️⃣ **Network Troubleshooting**

If DNS still fails:

**A. Try Different Network**
```bash
# Switch to mobile hotspot and test
ping db.cbskaefmgmcyhrblsgez.supabase.co
```

**B. Force IPv4**
```bash
# Add to ~/.zshrc or ~/.bashrc
export PGHOSTADDR=0.0.0.0
export PSQL_HOSTADDR_LOOKUP=1

# Then restart terminal
```

**C. Use Cloudflare DNS**
```bash
# Change DNS to Cloudflare (often fixes Supabase DNS issues)
# System Preferences → Network → Advanced → DNS
# Add: 1.1.1.1 and 1.0.0.1
```

**D. Check if Project is Paused**
- Go to Supabase Dashboard
- Check if project shows "Paused" status
- If paused, resume it

### 4️⃣ **Alternative: Use Supabase Dashboard SQL Editor**

When the web UI works (even if CLI doesn't):

1. Go to: https://supabase.com/dashboard/project/cbskaefmgmcyhrblsgez
2. Click "SQL Editor" in sidebar
3. Click "New query"
4. Copy/paste migration files in order:
   - `backend/supabase/migrations/025a_fix_analytics_schema_part1.sql`
   - `backend/supabase/migrations/025b_fix_analytics_schema_part2.sql`
   - `backend/supabase/migrations/025c_fix_analytics_schema_part3.sql`
5. Run each one

## 📋 Quick Test Commands

```bash
# Test 1: Can you reach Supabase at all?
curl -I https://cbskaefmgmcyhrblsgez.supabase.co

# Test 2: Does pooler hostname resolve?
ping cbskaefmgmcyhrblsgez.pooler.supabase.com

# Test 3: Does direct hostname resolve?
ping db.cbskaefmgmcyhrblsgez.supabase.co

# Test 4: Test pooler port
nc -vz cbskaefmgmcyhrblsgez.pooler.supabase.com 6543

# Test 5: Test direct port (if hostname resolves)
nc -vz db.cbskaefmgmcyhrblsgez.supabase.co 5432
```

## 🎯 Recommended Next Steps

1. **Get your database password** from Supabase Dashboard
2. **Test pooler hostname**: `ping cbskaefmgmcyhrblsgez.pooler.supabase.com`
3. **If pooler resolves**: Run the migration script
4. **If pooler also fails**: Try mobile hotspot or different network
5. **If still failing**: Use Dashboard SQL Editor when web UI works

## 📝 Current Status

- ✅ Migration files ready and optimized
- ✅ Script created with pooler support
- ✅ Environment variables configured
- ⏳ Waiting for DNS resolution or network fix
- ✅ Backend handles missing columns gracefully (app works without migrations)

## 💡 Why This Happens

Supabase uses different hostnames for different services:
- `*.supabase.co` → HTTPS API (works)
- `db.*.supabase.co` → Direct PostgreSQL (DNS failing)
- `*.pooler.supabase.com` → Transaction pooler (should try this)

Network/DNS issues can affect one but not the other. The pooler often works when direct connection doesn't.


