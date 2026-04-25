---
title: OpenIncident
emoji: "🚨"
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Production Incident Debugging Environment

## Hackathon Quick Links

- Hugging Face Space: https://huggingface.co/spaces/thanayr/OpenIncident
- Minimal HF TRL notebook path: `colab/OpenIncidentX_HF_TRL_Minimal.ipynb`
- Colab notebook link: https://colab.research.google.com/drive/1R4IrMr5nIKm7lZfbI08EP9ijkUgF7fxH?usp=sharing
- RL baseline + training runner: `colab/run_openincident_hackathon.py`
- HF TRL minimal trainer: `colab/run_openincident_hf_trl_minimal.py`
- Final submission guide: `docs/HACKATHON_SUBMISSION_FINAL.md`
- Final result summary: `docs/HACKATHON_RESULTS.md`
- Final judge story README: `README_HACKATHON_FINAL.md`
- Public deployment guide: `docs/DEPLOY_PUBLIC.md`
- Command pack: `docs/RUN_COMMANDS.md`
- Production app container: `Dockerfile.app`
- Demo video link (replace before final submission): `TODO_ADD_VIDEO_URL`
- Hugging Face blog link (replace before final submission): `TODO_ADD_BLOG_URL`

## Project Description

This project is an OpenEnv-style environment for evaluating AI agents on realistic production incident response. The agent behaves like an on-call backend engineer: it inspects evidence, identifies root cause, applies mitigation, restores service health, and adds follow-up monitoring.

The local product-dev version also includes:

- project registration for real websites
- health/API/browser validation checks
- automatic incident creation from failed checks
- run triage summaries
- Playwright-backed rendered browser checks

## Motivation

Production incident response is a real, high-value engineering workflow with clear operational tradeoffs. Good agents must diagnose ambiguous evidence, avoid harmful actions, recover the system quickly, and leave the service safer than before.

## Observation Space

The environment state includes:

- `incident_id`
- `difficulty`
- `service_name`
- `incident_summary`
- `current_status`
- `severity`
- `user_impact`
- `logs`
- `metrics`
- `traces`
- `recent_deploys`
- `config_snapshot`
- `code_snippet`
- `available_dashboards`
- `investigation_notes`
- `suspected_root_cause`
- `root_cause_confirmed`
- `mitigation_applied`
- `service_restored`
- `monitoring_added`
- `passed_checks`
- `failed_checks`
- `reliability_score`
- `steps_taken`
- `max_steps`
- `last_action`
- `last_action_error`

## Action Space

Allowed actions:

- `inspect_logs`
- `inspect_metrics`
- `inspect_traces`
- `inspect_deploys`
- `inspect_config`
- `inspect_code`
- `identify_root_cause`
- `apply_fix`
- `rollback_deploy`
- `restart_service`
- `scale_service`
- `add_monitor`
- `resolve_incident`
- `do_nothing`

## Tasks

### Easy

`profile-service`: null handling bug after a deployment causes profile requests to return 500 errors.

### Medium

`checkout-service`: stale checkout pricing caused by overlong cache TTL plus missing invalidation logic.

### Hard

`search-service`: timeout storm caused by a feature-flagged N+1 query pattern combined with too-low worker concurrency.

## Reward Design

The reward combines:

- immediate action reward
- passed and failed operational checks
- root cause confirmation
- service restoration
- monitoring addition
- reliability score

Rewards are clamped to `0.0-1.0`.

## How To Run

### Local

```bash
pip install fastapi "uvicorn[standard]" pydantic openai requests pyyaml playwright
python -m playwright install chromium
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Backend Storage

The backend now uses a SQLite-backed state database by default:

```text
data/openincident.db
```

You can override it with:

```bash
OPENINCIDENT_DATABASE_URL=sqlite:///data/openincident.db
```

If you already have an older JSON store at `data/openincident_store.json`, the backend will import it into SQLite on first startup.

Useful health endpoints:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/system/status
```

Database inspection endpoints for authenticated operators:

```text
GET /system/database/overview
GET /system/database/migrations
GET /system/database/{table_name}?limit=50
```

Supported table names:

- `app_state`
- `auth_accounts`
- `auth_tokens`
- `projects`
- `stories`
- `runs`
- `project_logs`
- `project_metrics`
- `project_events`

### Neon / Postgres

Neon Postgres is the intended database target for this project.
The backend can also run with SQLite locally, but that is only a fallback for development.

Set the connection string as:

```bash
OPENINCIDENT_DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST/DATABASE?sslmode=require&channel_binding=require
```

Once the Postgres driver is installed, the same backend state store will use Neon instead of the local SQLite file.

For local development, you can also copy:

```text
.env.backend.example -> .env.backend
```

and place `OPENINCIDENT_DATABASE_URL` there. The backend will load `.env.backend` automatically on startup.

### Dashboard

Open the dashboard locally at:

```text
http://127.0.0.1:8000/dashboard
```

For real frontend checks, choose `Playwright rendered check` in the browser-check form.

### React Command Center

A separate React frontend now lives in `frontend/`.

Run it in a second terminal:

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Then open:

```text
http://127.0.0.1:5173
```

By default the React app talks to the FastAPI backend at `http://127.0.0.1:8000`.

If the login screen shows a backend fetch error, make sure the FastAPI server is running first and that `http://127.0.0.1:8000/health` returns a healthy response.

### Build The React App Into FastAPI

If you want the React command center served directly by FastAPI on `/dashboard`, build it first:

```bash
cd frontend
npm install
npm run build
```

After that, restart the backend and open:

```text
http://127.0.0.1:8000/dashboard
```

FastAPI will serve the built React app when `frontend/dist` exists. If it does not exist yet, it falls back to the legacy static dashboard.

### Smoke Test

```powershell
@'
from client import OpenEnvClient

client = OpenEnvClient()
print(client.reset(task_id="easy"))
print(client.step("inspect_logs"))
print(client.step("inspect_code"))
print(client.step("identify_root_cause", content="Null input reaches strip() without a guard"))
print(client.step("apply_fix", content="add null guard to normalize_display_name"))
print(client.step("resolve_incident"))
'@ | python -
```

### Real-World Signal Ingestion

You can stream real logs and metrics into project datasets with:

```powershell
python scripts/realtime_ingest_bridge.py --help
```

Quick usage guide:

- [docs/REALWORLD_DATA_INGESTION.md](C:/My%20Projects/AgenEnv/docs/REALWORLD_DATA_INGESTION.md)

### Baseline Inference

Set these environment variables before running:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

Then run:

```bash
python inference.py
```

### Docker

```bash
docker build -t production-incident-env .
docker run -p 8000:7860 production-incident-env
```

The Docker image now builds the React frontend and serves it from FastAPI at `/dashboard`.

## Baseline Scores

Deterministic fallback policy targets:

- `easy`: expected final score near `1.00`
- `medium`: expected final score near `1.00`
- `hard`: expected final score near `1.00`

## Sample Logs

```text
[START] task=easy env=production_incident_debugging model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=inspect_logs reward=0.11 done=false error=null
[END] success=true steps=5 score=1.00 rewards=0.11,0.16,0.61,1.00,1.00
```
