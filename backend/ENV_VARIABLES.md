# Backend Environment Variables Documentation

This document lists all environment variables needed to run the Chess GPT backend server.

## Required Variables

### OpenAI API Key
```bash
OPENAI_API_KEY=sk-your-openai-api-key-here
```
**Required:** Yes (for LLM features)  
**Description:** Your OpenAI API key for GPT models. Get one from https://platform.openai.com/api-keys  
**Note:** Backend will warn but continue without this if you're only using Stockfish analysis.

---

### Supabase Configuration (Choose ONE: Supabase OR Local PostgreSQL)

#### Option A: Supabase (Cloud or Local Supabase CLI)
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```
**Required:** Yes (for user profiles, game storage, analytics)  
**Description:** 
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Service role key (bypasses RLS, use server-side only)
**Note:** For local Supabase CLI, use `http://localhost:54321`

#### Option B: Local PostgreSQL (Direct Connection)
```bash
LOCAL_POSTGRES_URL=postgresql://postgres:password@localhost:5432/chess_gpt_local
```
**Required:** Yes (alternative to Supabase)  
**Description:** Direct PostgreSQL connection string. Format: `postgresql://user:password@host:port/database`  
**Note:** If both `SUPABASE_URL` and `LOCAL_POSTGRES_URL` are set, `LOCAL_POSTGRES_URL` takes precedence.

---

## Optional Variables

### Server Configuration
```bash
BACKEND_PORT=8000
```
**Default:** `8000`  
**Description:** Port the backend server runs on. Used by tool executor for self-referencing URLs.

---

### Stockfish Engine
```bash
STOCKFISH_PATH=./stockfish
```
**Default:** `./stockfish` (in backend directory)  
**Description:** Path to Stockfish binary executable.  
**Note:** Make sure Stockfish is executable: `chmod +x stockfish`

---

### LLM Router Configuration (vLLM / RunPod)

#### vLLM Base URL (for self-hosted LLM)
```bash
VLLM_BASE_URL=https://your-runpod-proxy.runpod.net/v1
```
**Default:** `https://ap1nybhfb76r0o-8000.proxy.runpod.net/v1`  
**Description:** Base URL for vLLM-compatible API (RunPod, etc.)

#### vLLM API Key
```bash
VLLM_API_KEY=EMPTY
```
**Default:** `EMPTY`  
**Description:** API key for vLLM (usually not needed, but some proxies require it)

#### vLLM Model Path
```bash
VLLM_MODEL=/workspace/models/qwen2.5-32b-awq
```
**Default:** `/workspace/models/qwen2.5-32b-awq`  
**Description:** Model path/identifier for vLLM

#### vLLM Only Mode
```bash
VLLM_ONLY=true
```
**Default:** `true`  
**Description:** If `true`, only use vLLM (disable OpenAI fallback). Set to `false` to allow OpenAI fallback.

#### LLM Router Settings
```bash
LLM_SESSION_TTL_SECONDS=3600
LLM_ROUTER_LOG_CALLS=true
LLM_ROUTER_MEASURE_TTFT=true
VLLM_HEALTH_TTL_SECONDS=5
VLLM_CB_MAX_FAILS=3
VLLM_CB_WINDOW_S=30
VLLM_CB_COOLDOWN_S=30
```
**Description:** Circuit breaker and health check settings for vLLM router

---

### Redis Session Store (Optional - for multi-user persistence)

```bash
REDIS_URL=redis://localhost:6379/0
SESSION_STORE=memory
SESSION_TTL_SECONDS=3600
SESSION_MAX_CONTEXT_CHARS=250000
```
**Default:** `memory` (in-memory, no Redis needed)  
**Description:** 
- `REDIS_URL`: Redis connection string (only needed if `SESSION_STORE=redis`)
- `SESSION_STORE`: `redis` or `memory` (default: `memory`)
- `SESSION_TTL_SECONDS`: Session expiration time
- `SESSION_MAX_CONTEXT_CHARS`: Max characters in session context

**Note:** Redis is only needed if you want session persistence across server restarts or multi-instance deployments.

---

### Personal Review Configuration

```bash
PERSONAL_REVIEW_REPORTER_MODEL=gpt-5-mini
PERSONAL_REVIEW_PLANNER_MODEL=gpt-4o-mini
PERSONAL_REVIEW_DEFAULT_DEPTH=15
PERSONAL_REVIEW_MAX_GAMES=50
PERSONAL_REVIEW_CACHE_TTL=86400
PERSONAL_REVIEW_MAX_PARALLEL=4
PERSONAL_REVIEW_RATE_LIMIT=10
```
**Description:** Configuration for personal game review features

---

### Explainer Configuration

```bash
EXPLAINER_MODEL=gpt-4o-mini
EXPLAINER_MAX_TOKENS=1600
STRICT_LLM_MODE=false
```
**Description:** Model and settings for move explanation features

---

### Investigator Configuration

```bash
INVESTIGATOR_DEBUG=0
INVESTIGATOR_EVIDENCE_MAX_PLIES=8
```
**Description:** Debug and evidence gathering settings

---

### Memory & Summarization

```bash
MEMORY_COMPRESS_MAX_TOKENS=350
SUMMARIZE_FACTS_MAX_TOKENS=450
SELF_CHECK_MAX_TOKENS=250
```
**Description:** Token limits for various LLM operations

---

### NNUE & Analysis

```bash
NNUE_DUMP_TIMEOUT_S=8
ENABLE_CLAIM_NNUE_TAG_RELEVANCE=true
```
**Description:** NNUE evaluation dump timeout and tag relevance settings

---

### Legacy Features

```bash
ENABLE_LEGACY_PRECOMPUTE_ANALYSIS_REQUESTS=false
```
**Default:** `false`  
**Description:** Enable legacy precomputation mode (usually not needed)

---

### Redis Seed Prefix Reset

```bash
ALLOW_SEED_PREFIX_RESET=true
```
**Default:** `true`  
**Description:** Allow resetting seed prefix in Redis sessions (for development)

---

### Database Password (for migrations)

```bash
SUPABASE_DB_PASSWORD=your-postgres-password
```
**Description:** PostgreSQL password for direct database migrations (scripts only)

---

## Example .env File

Create a `.env` file in the `backend/` directory with your values:

```bash
# ============================================
# REQUIRED - Core Configuration
# ============================================

# OpenAI API Key (required for LLM features)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Database: Choose ONE option below

# Option A: Supabase (Cloud)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Option B: Local PostgreSQL (alternative to Supabase)
# LOCAL_POSTGRES_URL=postgresql://postgres:password@localhost:5432/chess_gpt_local

# ============================================
# OPTIONAL - Server Configuration
# ============================================

BACKEND_PORT=8000
STOCKFISH_PATH=./stockfish

# ============================================
# OPTIONAL - vLLM / RunPod (if using self-hosted LLM)
# ============================================

# VLLM_BASE_URL=https://your-runpod-proxy.runpod.net/v1
# VLLM_API_KEY=EMPTY
# VLLM_MODEL=/workspace/models/qwen2.5-32b-awq
# VLLM_ONLY=true

# ============================================
# OPTIONAL - Redis (for session persistence)
# ============================================

# REDIS_URL=redis://localhost:6379/0
# SESSION_STORE=memory
# SESSION_TTL_SECONDS=3600

# ============================================
# OPTIONAL - Feature Tuning
# ============================================

# PERSONAL_REVIEW_DEFAULT_DEPTH=15
# PERSONAL_REVIEW_MAX_GAMES=50
# EXPLAINER_MODEL=gpt-4o-mini
# INVESTIGATOR_DEBUG=0
```

---

## Minimum Setup (Quick Start)

For a basic setup, you only need:

```bash
OPENAI_API_KEY=sk-your-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-key
```

Everything else will use sensible defaults.

---

## Security Notes

⚠️ **IMPORTANT:**
- Never commit `.env` files to git
- `SUPABASE_SERVICE_ROLE_KEY` bypasses Row Level Security - keep it secret
- `OPENAI_API_KEY` has billing access - protect it
- Use environment variables or secrets manager in production
- For local development, `.env` files are fine

---

## Environment Variable Priority

1. System environment variables (highest priority)
2. `.env` file in `backend/` directory
3. Default values in code (lowest priority)

---

## Troubleshooting

### Backend won't start
- Check that `OPENAI_API_KEY` is set (or accept warnings)
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are correct
- Ensure `STOCKFISH_PATH` points to executable binary

### Database connection fails
- Verify Supabase credentials are correct
- If using local PostgreSQL, check connection string format
- Ensure database is running and accessible

### LLM features not working
- Check `OPENAI_API_KEY` is valid
- If using vLLM, verify `VLLM_BASE_URL` is accessible
- Check `VLLM_ONLY` setting matches your setup

---

## Production Deployment

For production servers, set environment variables via:
- **Docker:** `docker run -e OPENAI_API_KEY=...`
- **Systemd:** `Environment=OPENAI_API_KEY=...` in service file
- **Cloud platforms:** Use their secrets/environment variable UI
- **Never:** Hardcode secrets in code or commit `.env` files
