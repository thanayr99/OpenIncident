# Deploy OpenIncident X Publicly

This guide deploys OpenIncident X so anyone can use it.

## What you get

- FastAPI backend + agent orchestration
- React command center UI
- One-click instant simulation demo on the launch screen
- Public URLs you can share with judges/users

## Option A (Recommended): Single service deployment

Use one container that serves backend + built frontend from the same URL.

### 1. Build image locally (sanity check)

```powershell
docker build -f Dockerfile.app -t openincident-x:latest .
docker run -p 8000:8000 openincident-x:latest
```

Open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/dashboard`

### 2. Deploy to Railway/Render/Fly (container mode)

Use `Dockerfile.app`.

Set environment variables:

- `OPENINCIDENT_DATABASE_URL`  
  Example Neon:
  `postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require&channel_binding=require`
- `OPENINCIDENT_ALLOWED_ORIGINS`  
  For same-origin single-service deploy, set to your app URL:
  `https://your-openincident-domain`

Optional:

- `OPENAI_API_KEY` (if you later enable LLM-backed extensions)

### 3. Verify production

Hit:

- `/health`
- `/system/status`
- `/dashboard`

Then on launch screen click `Run instant agent demo`.

## Option B: Split deployment (Frontend + Backend)

Use this only if you specifically want Vercel frontend and Railway backend.

### Backend (Railway/Render)

Deploy backend container with `Dockerfile.app` or run `uvicorn server.app:app`.

Set:

- `OPENINCIDENT_DATABASE_URL`
- `OPENINCIDENT_ALLOWED_ORIGINS=https://your-frontend.vercel.app`

### Frontend (Vercel)

Project root for Vercel: `frontend/`

Set build env var:

- `VITE_API_BASE_URL=https://your-backend-domain`

Optional demo-template env vars:

- `VITE_DEMO_REPOSITORY_URL`
- `VITE_DEMO_FRONTEND_URL`
- `VITE_DEMO_BACKEND_URL`

## Smoke test checklist

1. Register/login works.
2. Create project works.
3. `Demo run` button works in sidebar.
4. Launch page `Run instant agent demo` works.
5. `GET /projects`, `/summary`, `/stories`, `/runs` succeed.
6. No CORS errors in browser console.

## Common issues

- `failed to resolve host 'HOST'`:
  your DB URL still has placeholder values. Set real `OPENINCIDENT_DATABASE_URL`.
- Frontend cannot reach backend:
  set `VITE_API_BASE_URL` to public backend URL.
- Browser checks fail in cloud:
  ensure container includes Playwright install (already in `Dockerfile.app`).
