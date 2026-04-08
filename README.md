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

## Project Description

This project is an OpenEnv-style environment for evaluating AI agents on realistic production incident response. The agent behaves like an on-call backend engineer: it inspects evidence, identifies root cause, applies mitigation, restores service health, and adds follow-up monitoring.

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
pip install fastapi "uvicorn[standard]" pydantic openai requests pyyaml
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

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
