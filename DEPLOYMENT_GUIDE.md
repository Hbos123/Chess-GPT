# Deployment Guide: Vercel (Frontend) + Render (Backend)

This guide walks you through deploying Chess GPT to production.

## Prerequisites

- GitHub repository with your code
- Vercel account (free tier works)
- Render account (free tier works)
- Supabase project (or PostgreSQL database)
- OpenAI API key

---

## Part 1: Deploy Backend to Render

### Step 1: Connect Repository to Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Select the repository and branch

### Step 2: Configure Render Service

**Basic Settings:**
- **Name:** `chess-gpt-backend` (or your preferred name)
- **Region:** Choose closest to your users (e.g., `Oregon`, `Frankfurt`)
- **Branch:** `main` (or your default branch)
- **Root Directory:** `backend` (if your backend code is in a `backend/` folder)
- **Environment:** `Python 3`
- **Build Command:** (Render will auto-detect from `render.yaml`, or use):
  ```bash
  pip install --upgrade pip && pip install -r requirements.txt
  ```
- **Start Command:**
  ```bash
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```

**Advanced Settings:**
- **Health Check Path:** `/health`
- **Plan:** `Starter` (free tier) or upgrade for production

### Step 3: Set Environment Variables in Render

Go to **Environment** tab and add:

**Required:**
```
OPENAI_API_KEY=sk-your-openai-api-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

**Important:** Before deploying, ensure all Supabase migrations have been applied to your online Supabase database. See `APPLY_MIGRATIONS.md` for instructions.

**Optional (but recommended):**
```
STOCKFISH_PATH=./stockfish
ALLOWED_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com
PYTHON_VERSION=3.11.0
```

**Note:** `ALLOWED_ORIGINS` should include your Vercel frontend URL(s). You can add this after deploying the frontend.

### Step 4: Deploy

1. Click **"Create Web Service"**
2. Render will build and deploy your backend
3. Wait for deployment to complete (usually 2-5 minutes)
4. Copy your backend URL (e.g., `https://chess-gpt-backend.onrender.com`)

### Step 5: Test Backend

Visit: `https://your-backend.onrender.com/health`

You should see: `{"status":"ok"}`

---

## Part 2: Deploy Frontend to Vercel

### Step 1: Connect Repository to Vercel

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **"Add New..."** → **"Project"**
3. Import your GitHub repository
4. Select the repository

### Step 2: Configure Vercel Project

**Framework Preset:** Next.js (auto-detected)

**Root Directory:** 
- If frontend code is in `frontend/` folder: set to `frontend`
- If frontend code is at root: leave empty

**Build Settings:**
- **Build Command:** `npm run build` (or `cd frontend && npm run build` if root directory is set)
- **Output Directory:** `.next` (auto-detected)
- **Install Command:** `npm install` (or `cd frontend && npm install`)

### Step 3: Set Environment Variables in Vercel

Go to **Settings** → **Environment Variables** and add:

```
NEXT_PUBLIC_BACKEND_URL=https://your-backend.onrender.com
```

Replace `your-backend.onrender.com` with your actual Render backend URL.

**Important:** 
- Add this for **Production**, **Preview**, and **Development** environments
- After adding, redeploy your frontend for changes to take effect

### Step 4: Deploy

1. Click **"Deploy"**
2. Vercel will build and deploy your frontend
3. Wait for deployment (usually 1-3 minutes)
4. Copy your frontend URL (e.g., `https://chess-gpt.vercel.app`)

### Step 5: Update Backend CORS

Go back to Render dashboard → **Environment** → Add/Update:

```
ALLOWED_ORIGINS=https://your-app.vercel.app
```

Replace with your actual Vercel URL. If you have multiple domains, separate with commas:

```
ALLOWED_ORIGINS=https://chess-gpt.vercel.app,https://your-custom-domain.com
```

**Redeploy** the backend after adding this variable.

---

## Part 3: Custom Domain (Optional)

### Vercel Custom Domain

1. Go to Vercel project → **Settings** → **Domains**
2. Add your custom domain
3. Follow DNS configuration instructions
4. Update `NEXT_PUBLIC_BACKEND_URL` if needed

### Render Custom Domain

1. Go to Render service → **Settings** → **Custom Domains**
2. Add your custom domain
3. Follow DNS configuration instructions
4. Update `ALLOWED_ORIGINS` in Render environment variables

---

## Troubleshooting

### Backend Issues

**"Module not found" errors:**
- Ensure `requirements.txt` includes all dependencies
- Check that `Root Directory` in Render is set correctly

**"Stockfish not found" errors:**
- The `render.yaml` includes automatic Stockfish download
- Or commit Stockfish binary to your repo
- Or set `STOCKFISH_PATH` environment variable

**CORS errors:**
- Verify `ALLOWED_ORIGINS` includes your Vercel URL
- Check that backend was redeployed after adding `ALLOWED_ORIGINS`
- Verify frontend is using correct `NEXT_PUBLIC_BACKEND_URL`

**Port errors:**
- Render sets `PORT` automatically - don't hardcode port 8000
- The code now uses `os.getenv("PORT", "8000")` which works correctly

### Frontend Issues

**"Backend not available" errors:**
- Verify `NEXT_PUBLIC_BACKEND_URL` is set correctly in Vercel
- Check that backend is running: visit `https://your-backend.onrender.com/health`
- Ensure backend URL doesn't have trailing slash
- Redeploy frontend after changing environment variables

**Build errors:**
- Check that `Root Directory` is set correctly
- Verify `package.json` exists in the correct location
- Check build logs in Vercel dashboard

**CORS errors in browser:**
- Backend CORS must include your Vercel domain
- Check browser console for exact CORS error message
- Verify `allow_credentials=True` is set in backend CORS config

---

## Environment Variables Reference

### Backend (Render)

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for LLM features |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `ALLOWED_ORIGINS` | Recommended | Comma-separated list of allowed frontend origins |
| `STOCKFISH_PATH` | Optional | Path to Stockfish binary (defaults to `./stockfish`) |
| `PORT` | Auto-set | Port number (Render sets this automatically) |

### Frontend (Vercel)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | Yes | Full URL to your Render backend (e.g., `https://backend.onrender.com`) |

---

## Quick Checklist

### Backend (Render)
- [ ] Repository connected to Render
- [ ] Root directory set to `backend` (if applicable)
- [ ] Build command configured
- [ ] Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] Health check path: `/health`
- [ ] Environment variables set (OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
- [ ] Backend deployed and `/health` endpoint works
- [ ] Backend URL copied

### Frontend (Vercel)
- [ ] Repository connected to Vercel
- [ ] Root directory set correctly
- [ ] Framework preset: Next.js
- [ ] Environment variable `NEXT_PUBLIC_BACKEND_URL` set
- [ ] Frontend deployed
- [ ] Frontend URL copied

### Post-Deployment
- [ ] `ALLOWED_ORIGINS` added to Render with Vercel URL
- [ ] Backend redeployed after adding `ALLOWED_ORIGINS`
- [ ] Test frontend → backend connection
- [ ] Check browser console for errors
- [ ] Test key features (chess board, chat, etc.)

---

## Cost Estimates

**Render (Free Tier):**
- 750 hours/month free
- Service spins down after 15 minutes of inactivity
- First request after spin-down takes ~30 seconds (cold start)

**Vercel (Free Tier):**
- Unlimited deployments
- 100GB bandwidth/month
- Perfect for Next.js apps

**Upgrade Options:**
- Render Starter: $7/month (always-on, no cold starts)
- Vercel Pro: $20/month (more bandwidth, better performance)

---

## Support

If you encounter issues:
1. Check Render deployment logs
2. Check Vercel build logs
3. Test backend health endpoint
4. Check browser console for frontend errors
5. Verify all environment variables are set correctly
