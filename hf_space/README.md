---
title: OpenIncident X
emoji: fire_engine
colorFrom: red
colorTo: blue
sdk: gradio
sdk_version: 5.29.0
app_file: app.py
pinned: false
---

# OpenIncident X

OpenIncident X is an OpenEnv-compatible multi-agent professional-operations
environment for training LLMs on long-horizon incident response.

This Space is the lightweight hackathon presentation layer for the project.

## What This Demo Shows

- environment framing
- action space and incident lifecycle
- RL baseline vs trained comparison
- mandatory HF TRL training path (Colab-runnable)

## Core Idea

The trained agent does not begin with full ground truth.
It must inspect a partially observable software-operations world and decide
when to:

- inspect logs
- inspect metrics
- inspect traces
- inspect deploy context
- inspect code and config
- apply a fix
- rollback a deploy
- restart service
- resolve the incident

## Main Environment

The primary environment is:

- `ProductionIncidentEnv`

And the main trained agent for the hackathon is:

- `Reliability Agent`

## Current RL Result (Stochastic Medium)

From `artifacts/colab_demo/medium_epsilon_metrics.json`:

- baseline success rate: `0.00%`
- trained success rate: `33.33%`
- baseline avg env reward: `0.6276`
- trained avg env reward: `1.6891`
- trained root cause rate: `63.33%`
- trained restore rate: `43.33%`
- trained closure gap rate: `10.00%`

## Important Honesty Note

The stochastic mode is intentionally harder than deterministic mode. The model
does not solve every episode, but it demonstrates measurable improvement over
baseline in a non-trivial setup.

## Mandatory HF TRL / Colab Path

Minimal TRL script:

- `colab/run_openincident_hf_trl_minimal.py`

Minimal notebook path:

- `colab/OpenIncidentX_HF_TRL_Minimal.ipynb`

Command:

```bash
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```

## Local / Colab Repro (RL Baseline + Q-learning)

Recommended command:

```bash
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --output-dir artifacts/colab_demo
```

## Dependency Pin

`openenv-core==0.2.3` is pinned in `pyproject.toml`.
