# Quick Deployment Checklist

## Backend (Render)

1. **Connect Repository**
   - Go to Render → New Web Service
   - Connect GitHub repo
   - Root Directory: `backend`

2. **Set Environment Variables**
   ```
   OPENAI_API_KEY=sk-...
   SUPABASE_URL=https://...
   SUPABASE_SERVICE_ROLE_KEY=...
   ALLOWED_ORIGINS=https://your-app.vercel.app
   ```

3. **Build/Start Commands** (auto-detected from `render.yaml`)
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

4. **Deploy** → Copy backend URL

---

## Frontend (Vercel)

1. **Connect Repository**
   - Go to Vercel → Add Project
   - Import GitHub repo
   - Root Directory: `frontend` (if frontend is in subfolder)

2. **Set Environment Variable**
   ```
   NEXT_PUBLIC_BACKEND_URL=https://your-backend.onrender.com
   ```

3. **Deploy** → Copy frontend URL

4. **Update Backend CORS**
   - Add frontend URL to `ALLOWED_ORIGINS` in Render
   - Redeploy backend

---

## Test

- Backend: `https://your-backend.onrender.com/health` → `{"status":"ok"}`
- Frontend: Visit URL, check browser console for errors
