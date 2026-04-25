# OpenIncident X Command Pack

Use these exact commands for local run, demo run, training, and deployment.

## 1) Backend (FastAPI)

```powershell
cd "C:\My Projects\AgenEnv"
Copy-Item .env.backend.example .env.backend
python -m pip install -e .
python -m playwright install chromium
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

Check:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/dashboard`

## 2) Frontend (Vite)

```powershell
cd "C:\My Projects\AgenEnv\frontend"
npm install
Copy-Item .env.example .env
npm run dev
```

Open:

- `http://127.0.0.1:5173`

### 2a) If `localhost:5173` shows 404

This means another process is already bound to port `5173` (not your Vite app), or Vite did not start.

Use:

```powershell
netstat -ano | findstr :5173
```

If a stale process is shown, stop it (run terminal as Administrator if needed):

```powershell
taskkill /PID <PID_FROM_NETSTAT> /F
```

Then start Vite on a known free port:

```powershell
cd "C:\My Projects\AgenEnv\frontend"
npm run dev -- --host 0.0.0.0 --port 5174 --strictPort
```

Open:

- `http://127.0.0.1:5174`

## 3) One-click demo

From launch screen click:

- `Run instant agent demo` (works without creating a project)

From command center:

- `Demo run` in left sidebar (project-based full workflow)

## 4) RL run (hackathon)

```powershell
cd "C:\My Projects\AgenEnv"
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo_v1
python colab/run_openincident_hackathon.py --task-id medium --episodes 40 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v2 --output-dir artifacts/colab_demo_v2
```

## 5) HF TRL minimal run

```powershell
cd "C:\My Projects\AgenEnv"
$env:PYTHONUTF8='1'
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --env-profile v2 --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal_v2
```

## 6) Build frontend for production

```powershell
cd "C:\My Projects\AgenEnv\frontend"
npm run build
```

## 7) Build single-container production image

```powershell
cd "C:\My Projects\AgenEnv"
docker build -f Dockerfile.app -t openincident-x:latest .
docker run -p 8000:8000 openincident-x:latest
```

## 8) Public deploy guide

See:

- `docs/DEPLOY_PUBLIC.md`

## 9) Splunk production log connector (OpenIncident)

Backend must be running first (`:8000`) and you must have a project id.

Quick one-command setup:

```powershell
python scripts/configure_splunk_connector.py `
  --api-base-url http://127.0.0.1:8000 `
  --email your@email.com `
  --project-id YOUR_PROJECT_ID `
  --splunk-url "https://YOUR_SPLUNK_HOST:8089/services/search/jobs/export" `
  --splunk-token "YOUR_SPLUNK_TOKEN" `
  --search "search index=main | head 100" `
  --pull-limit 100
```

1. Save Splunk connector config:

```powershell
$token = "YOUR_OPENINCIDENT_BEARER_TOKEN"
$projectId = "YOUR_PROJECT_ID"

$headers = @{ Authorization = "Bearer $token" }

Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8000/projects/$projectId/logs/connector" -Headers $headers -ContentType "application/json" -Body (@{
  url = "https://YOUR_SPLUNK_HOST:8089/services/search/jobs/export"
  method = "POST"
  headers = @{
    Authorization = "Splunk YOUR_SPLUNK_HEC_OR_SEARCH_TOKEN"
  }
  query_params = @{}
  payload = @{
    search = "search index=main | head 100"
    output_mode = "json"
    earliest_time = "-15m"
    latest_time = "now"
    count = "100"
  }
  payload_encoding = "form"
  enabled = $true
  format = "splunk_jsonl"
  entries_path = $null
  level_field = "level"
  source_field = "source"
  message_field = "_raw"
  timestamp_field = "_time"
} | ConvertTo-Json -Depth 8)
```

2. Pull logs now:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/projects/$projectId/logs/connector/pull" -Headers $headers -ContentType "application/json" -Body (@{
  limit = 100
} | ConvertTo-Json -Depth 4)
```

3. Trigger diagnosis sweep in UI:

- Go to `Execution`
- Click `Triage active incident` or `Run diagnosis sweep`
