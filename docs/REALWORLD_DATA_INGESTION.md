# Real-World Data Ingestion (Logs + Metrics)

This guide connects real deployment signals to OpenIncident datasets.

## What This Script Does

`scripts/realtime_ingest_bridge.py`:

1. logs in to your OpenIncident backend
2. resolves your project id (via id or name)
3. tails one or more local log files
4. optionally pulls numeric metrics from a JSON endpoint
5. pushes both into:
   - `POST /projects/{project_id}/logs`
   - `POST /projects/{project_id}/metrics`
6. repeats on an interval (or once)

## Quick Start

From repo root:

```powershell
python scripts/realtime_ingest_bridge.py `
  --api-base-url http://127.0.0.1:8000 `
  --email your@email.com `
  --password "your_password" `
  --project-name "HouseSafe AI" `
  --log-file "C:\path\to\app.log" `
  --metrics-endpoint "https://your-service.com/metrics.json" `
  --interval-seconds 60
```

Or use env vars (safer for terminal history):

```powershell
$env:OPENINCIDENT_API_BASE_URL = "http://127.0.0.1:8000"
$env:OPENINCIDENT_EMAIL = "your@email.com"
$env:OPENINCIDENT_PASSWORD = "your_password"
$env:OPENINCIDENT_PROJECT_NAME = "HouseSafe AI"

python scripts/realtime_ingest_bridge.py `
  --log-file "C:\path\to\app.log" `
  --metrics-endpoint "https://your-service.com/metrics.json"
```

One-shot run:

```powershell
python scripts/realtime_ingest_bridge.py `
  --api-base-url http://127.0.0.1:8000 `
  --email your@email.com `
  --password "your_password" `
  --project-name "HouseSafe AI" `
  --log-file "C:\path\to\app.log" `
  --once
```

## Useful Options

- `--project-id` use explicit project id instead of name
- `--log-file` repeat multiple times for multiple files
- `--metrics-endpoint` JSON endpoint with numeric values
- `--metrics-path` pick specific JSON paths only (repeatable)
- `--metric name=value` push static metrics (repeatable)
- `--state-file` persist tail offsets
- `--insecure` disable TLS verification for internal environments

## Example: Metrics Path Selection

If endpoint returns:

```json
{
  "service": {
    "latency_ms": 230.4,
    "error_rate": 1.7
  },
  "queue_depth": 12
}
```

Run:

```powershell
python scripts/realtime_ingest_bridge.py `
  --api-base-url http://127.0.0.1:8000 `
  --email your@email.com `
  --password "your_password" `
  --project-name "HouseSafe AI" `
  --metrics-endpoint "https://your-service.com/metrics.json" `
  --metrics-path "service.latency_ms" `
  --metrics-path "service.error_rate" `
  --metric "deploy_build_age_minutes=5"
```

## Real-World Deployment Pattern

For production:

1. expose a small JSON metrics endpoint from your app/monitoring adapter
2. write runtime logs to files or export them locally on the collector host
3. run `realtime_ingest_bridge.py` as a service (systemd, PM2, scheduled task)
4. keep interval at 30-120s
5. monitor `state-file` and script output for ingestion health

## One Project, Multiple URLs (Frontend + Backend)

You can keep frontend and backend under one OpenIncident project by configuring project endpoints.

UI mapping in the dashboard:

- `Frontend URL` = your Vercel app URL
- `Backend API URL` = your Railway/Fly/VM API URL
- `Backend health path` = backend health endpoint (for example `/health`)

Example:

```powershell
$headers = @{ Authorization = "Bearer YOUR_TOKEN" }

Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8000/projects/YOUR_PROJECT_ID/endpoints" -Headers $headers -ContentType "application/json" -Body (@{
  endpoints = @(
    @{
      endpoint_id = "frontend"
      label = "Frontend Vercel"
      surface = "frontend"
      base_url = "https://your-frontend.vercel.app"
      healthcheck_path = "/"
    },
    @{
      endpoint_id = "backend"
      label = "Backend Railway"
      surface = "api"
      base_url = "https://your-backend.railway.app"
      healthcheck_path = "/health"
    }
  )
} | ConvertTo-Json -Depth 6)
```

Then checks auto-route by surface:

- browser checks prefer `frontend`
- API checks prefer `api`

Or force a specific endpoint with `endpoint_id` in check requests.

Example forced API check:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/projects/YOUR_PROJECT_ID/checks/api" -Headers $headers -ContentType "application/json" -Body (@{
  endpoint_id = "backend"
  method = "GET"
  path = "/health"
  expected_status = 200
  label = "Backend health"
} | ConvertTo-Json -Depth 6)
```

Example forced browser check:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/projects/YOUR_PROJECT_ID/checks/browser" -Headers $headers -ContentType "application/json" -Body (@{
  endpoint_id = "frontend"
  path = "/login"
  expected_text = "Login"
  browser_mode = "http"
  label = "Frontend login"
} | ConvertTo-Json -Depth 6)
```

## Verify Data Arrived

Use:

- `GET /projects/{project_id}/logs`
- `GET /projects/{project_id}/logs/summary`
- `GET /projects/{project_id}/metrics`
- `GET /projects/{project_id}/metrics/summary`
- `GET /projects/{project_id}/observability-training-dataset`

You should then see these signals in dashboard Evidence/Training views.

## Splunk Connector (Production)

OpenIncident now supports direct Splunk pull patterns through the log connector.

Recommended Splunk export endpoint:

- `https://<your-splunk-host>:8089/services/search/jobs/export`

Recommended connector settings:

- `method`: `POST`
- `format`: `splunk_jsonl`
- `payload_encoding`: `form`
- `message_field`: `_raw`
- `timestamp_field`: `_time`

### Fast Path (Recommended)

Use the helper script:

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

### API Example (PowerShell)

```powershell
$headers = @{ Authorization = "Bearer YOUR_OPENINCIDENT_TOKEN" }

Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8000/projects/YOUR_PROJECT_ID/logs/connector" -Headers $headers -ContentType "application/json" -Body (@{
  url = "https://YOUR_SPLUNK_HOST:8089/services/search/jobs/export"
  method = "POST"
  headers = @{
    Authorization = "Splunk YOUR_SPLUNK_TOKEN"
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

Then pull logs:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/projects/YOUR_PROJECT_ID/logs/connector/pull" -Headers $headers -ContentType "application/json" -Body (@{
  limit = 100
} | ConvertTo-Json -Depth 4)
```

Then run in UI:

1. Execution tab
2. `Run diagnosis sweep`
3. Review Evidence + agent handoff feed
