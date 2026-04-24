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

### A) RL Behavior Result (stochastic medium)

Source: `artifacts/colab_demo/medium_epsilon_metrics.json`

- baseline success rate: `0.00%`
- trained success rate: `33.33%`
- trained root-cause rate: `63.33%`
- trained restore rate: `43.33%`
- trained closure gap: `10.00%`

### B) HF TRL Pipeline Result (minimum requirement path)

Source: `artifacts/trl_minimal/medium_stochastic_trl_summary.json`

- dataset samples: `269`
- train runtime: `33.49s`
- train loss: `10.8209`
- model: `sshleifer/tiny-gpt2`

## 8) Reproducibility

RL run:

```powershell
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --output-dir artifacts/colab_demo
```

HF TRL run:

```powershell
$env:PYTHONUTF8='1'
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```

## 9) Submission Links

- GitHub: `https://github.com/thanayr99/OpenIncident`
- HF Space: `https://thanayr-openincident.hf.space`
- Colab: `https://colab.research.google.com/drive/1R4IrMr5nIKm7lZfbI08EP9ijkUgF7fxH?usp=sharing`

## 10) Honest Claim (Safe and Strong)

OpenIncident X shows measurable improvement in incident recovery and closure behavior in a stochastic, partially observable environment, with a working hosted Space and a reproducible HF TRL training path.
