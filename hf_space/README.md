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
- separate hackathon writeup in `Blog.MD`

## Hackathon Blog (Required Separate MD)

- `Blog.MD` (repo file)
- HF direct link: `https://huggingface.co/spaces/thanayr/OpenIncident/blob/main/Blog.MD`

## Final Video Script (With Results)

- `VIDEO_SCRIPT_FINAL.md` (repo file)
- HF direct link: `https://huggingface.co/spaces/thanayr/OpenIncident/blob/main/VIDEO_SCRIPT_FINAL.md`

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

## Official RL Result (Stochastic Medium, profile=v1)

From `artifacts/colab_demo_v1/medium_epsilon_metrics.json`:

- baseline success rate: `0.00%`
- trained success rate: `26.67%`
- baseline avg env reward: `0.6276`
- trained avg env reward: `1.0838`
- trained root cause rate: `63.33%`
- trained restore rate: `30.00%`
- trained closure gap rate: `3.33%`

## Harder Robustness Result (Stochastic Medium, profile=v2)

From `artifacts/colab_demo_v2_tuned4_full/medium_epsilon_v2_metrics.json`:

- baseline success rate: `0.00%`
- trained success rate: `27.50%`
- trained root cause rate: `86.25%`
- trained restore rate: `36.25%`
- trained closure gap rate: `8.75%`

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
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo_v1
```

Harder-profile command:

```bash
python colab/run_openincident_hackathon.py --task-id medium --episodes 80 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v2 --output-dir artifacts/colab_demo_v2_tuned4_full
```

## Dependency Pin

`openenv-core==0.2.3` is pinned in `pyproject.toml`.
