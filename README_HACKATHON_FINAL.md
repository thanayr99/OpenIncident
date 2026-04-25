# OpenIncident X: Final Judge Story

## 1) One-line Pitch

OpenIncident X is an OpenEnv-compatible, multi-agent incident-response environment where an LLM learns to investigate, diagnose, fix, and close production incidents under partial observability.

## 2) Why This Matters

Modern reliability work is not a single-step QA task. Real incidents require:

- incomplete evidence
- uncertain diagnosis
- action sequencing under risk
- closure discipline (restored + resolved, not half-finished)

This is exactly what OpenIncident X simulates and trains.

## 3) Theme Fit

Primary fit:

- `Theme #3.1 World Modeling (Professional Tasks)`

Secondary fit:

- `Theme #2 Long-Horizon Planning`
- `Theme #1 Multi-Agent Interactions`

## 4) The Agent Story (End-to-End Flow)

1. `Operator` signs in and creates a project.
2. `Planner Agent` classifies user stories and routes execution.
3. `Environment/Repo Agent` prepares code + runtime context.
4. `Frontend Test Agent` validates browser journeys.
5. `API Test Agent` validates backend contracts and health.
6. `Database Agent` reasons about persistence/data assumptions.
7. `Observability Agent` aggregates logs/metrics/traces evidence.
8. `Reliability Agent` runs incident handling inside `ProductionIncidentEnv`.
9. `Triage Agent` summarizes likely root cause and action path.
10. `Guardian Agent` gates release readiness.
11. `Oversight Agent` audits quality and confidence.

Core training target in this submission: `Reliability Agent`.

## 5) Environment Core

Main environment:

- `ProductionIncidentEnv` (`reset()`, `step(action)`)

Action space includes:

- inspect: logs, metrics, traces, deploys, config, code
- diagnose: identify root cause
- mitigate: apply fix / rollback / restart / scale / add monitor
- close: resolve incident

Modes:

- deterministic (sanity)
- stochastic (harder, judge-facing)

## 6) Reward Logic (What Behavior We Teach)

Reward promotes:

- evidence-based diagnosis
- valid mitigation
- verified recovery
- proper incident closure

Reward penalizes:

- premature fix attempts
- unsafe/no-op actions
- closure without restoration/verification

## 7) Training Evidence

### A) Official RL Result (stochastic medium, profile=v1)

Source: `artifacts/colab_demo_v1/medium_epsilon_metrics.json`

- baseline success rate: `0.00%`
- trained success rate: `33.33%`
- trained root-cause rate: `63.33%`
- trained restore rate: `43.33%`
- trained closure gap: `10.00%`

### A2) Robustness RL Result (stochastic medium, profile=v2 harder dynamics)

Source: `artifacts/colab_demo_v2_tuned4_full/medium_epsilon_v2_metrics.json`

- baseline success rate: `0.00%`
- trained success rate: `27.50%`
- trained root-cause rate: `86.25%`
- trained restore rate: `36.25%`
- trained closure gap: `8.75%`

### B) HF TRL Pipeline Result (minimum requirement path)

Source: `artifacts/trl_minimal/medium_stochastic_trl_summary.json`

- dataset samples: `269`
- train runtime: `27.91s`
- train loss: `10.8209`
- model: `sshleifer/tiny-gpt2`

## 8) Reproducibility

Official submission RL run (v1, stable judge packet):

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo_v1
```

Harder robustness RL run (v2, anti-shortcut profile):

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 80 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v2 --output-dir artifacts/colab_demo_v2_tuned4_full
```

HF TRL run:

```powershell
$env:PYTHONUTF8='1'
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```

HF TRL on V2 trajectories:

```powershell
$env:PYTHONUTF8='1'
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --env-profile v2 --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal_v2
```

## 9) Production-Ready Agent Guardrails

OpenIncident X now supports execution policy controls for project/session runs:

- `simulation`: full action execution (research/training mode)
- `recommend_only`: advisory mode (no action execution)
- `guarded`: allowlisted execution with approval token checks

PowerShell demo (replace token and IDs):

```powershell
$token = "<bearer_token>"
$headers = @{ Authorization = "Bearer $token" }

# Set project to guarded mode and require token for risky actions
$body = @{
  mode = "guarded"
  approval_token = "OPS-APPROVE-123"
  approval_required_actions = @("apply_fix", "rollback_deploy", "restart_service", "scale_service", "resolve_incident")
} | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri "http://localhost:8000/projects/<project_id>/execution-policy" -Headers $headers -ContentType "application/json" -Body $body

# Step without token (blocked)
$blocked = @{
  session_id = "<session_id>"
  action = @{ action_type = "apply_fix" }
} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/sessions/step" -Headers $headers -ContentType "application/json" -Body $blocked

# Step with token (allowed)
$allowed = @{
  session_id = "<session_id>"
  action = @{ action_type = "apply_fix" }
  approval_token = "OPS-APPROVE-123"
} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/sessions/step" -Headers $headers -ContentType "application/json" -Body $allowed
```

This lets you connect agents to real systems while preserving an explicit human approval boundary for high-risk actions.

## 10) Submission Links

- GitHub: `https://github.com/thanayr99/OpenIncident`
- HF Space: `https://thanayr-openincident.hf.space`
- Colab: `https://colab.research.google.com/drive/1R4IrMr5nIKm7lZfbI08EP9ijkUgF7fxH?usp=sharing`
- Public deployment guide: `docs/DEPLOY_PUBLIC.md`
- Command pack: `docs/RUN_COMMANDS.md`

## 11) Honest Claim (Safe and Strong)

OpenIncident X shows measurable improvement in incident recovery and closure behavior in a stochastic, partially observable environment, with a working hosted Space and a reproducible HF TRL training path.

## 12) Versioning Strategy (Safe Iteration)

- `v1` profile is the official judged benchmark packet (`artifacts/colab_demo_v1/*`).
- `v2` profile is the harder robustness packet (`artifacts/colab_demo_v2_tuned4_full/*`).
- Show both in submission: one for stable reproducibility, one for environment strength.
