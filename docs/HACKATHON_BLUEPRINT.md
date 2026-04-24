# OpenIncident X Hackathon Blueprint

## Goal

This document defines the **hackathon-first** version of OpenIncident X.

For the next 24 hours, this is the source of truth for what we are building,
what we are demoing, and what we are intentionally **not** spending time on.

## Recommended Theme Positioning

OpenIncident X fits best as:

1. `Theme #3.1 - World Modeling / Professional Tasks`
2. `Theme #2 - Super Long-Horizon Planning & Instruction Following`
3. `Theme #1 - Multi-Agent Interactions`

This is the clearest story:

OpenIncident X is an **OpenEnv-compatible multi-agent incident-response world**
for training and evaluating LLM agents on realistic software operations tasks:

- inspecting logs, metrics, traces, deploys, config, and code
- handling partial observability
- coordinating across specialist agents
- making long-horizon recovery decisions
- improving reward through training

## One-Sentence Problem Statement

Modern software incidents are long-horizon, partially observable, and require
coordinated multi-agent reasoning across frontend, API, runtime evidence, and
release-risk decisions. OpenIncident X turns this workflow into a trainable
OpenEnv environment for LLMs.

## What We Are Submitting

We are **not** submitting "a big dashboard with many features."

We are submitting:

1. a clear `OpenEnv` environment
2. a real action space
3. a coherent reward function
4. a minimal training script
5. evidence of reward improvement
6. a multi-agent professional-operations story

The dashboard is the **demo layer**, not the core submission.

## Core Submission Architecture

### 1. Main Environment

Primary environment:

- [environment.py](C:/My%20Projects/AgenEnv/server/environment.py)

Environment class:

- `ProductionIncidentEnv`

Key contract:

- `reset()`
- `step(action)`

This is the main environment we should present to judges.

### 2. Main Trained Agent

Primary trained agent:

- `Reliability Agent`

Why this is the correct training target:

- real sequential decisions
- meaningful action space
- sparse/delayed success
- real termination conditions
- measurable recovery quality

Current trainer:

- [rl_training.py](C:/My%20Projects/AgenEnv/rl_training.py)

### 3. Supporting Agents

The other agents should be presented as:

- environment-side specialists
- evaluators
- orchestrators
- data generators for future improvement

Important supporting agents:

- Planner Agent
- Environment Agent
- Frontend Test Agent
- API Test Agent
- Observability Agent
- Triage Agent
- Guardian Agent
- Oversight Agent

These strengthen the story of:

- multi-agent interaction
- long-horizon coordination
- professional workflow realism

But they are **not** the main RL target for this hackathon submission.

## What Makes The Environment Interesting

### Partial Observability

The agent does not begin with full ground truth.
It must inspect and infer from:

- logs
- metrics
- traces
- deploy context
- config
- code context

### Multi-Step Operational Recovery

The agent must decide when to:

- inspect more evidence
- identify root cause
- apply a fix
- restart service
- rollback deploy
- add monitoring
- resolve the incident

### Long-Horizon Structure

The agent can waste steps, act too early, or close too early.
That makes the environment meaningfully sequential and not just one-shot.

### Multi-Agent Framing

The environment is embedded inside a larger system where:

- Planner routes work
- Frontend/API agents generate validation signals
- Observability surfaces evidence
- Triage explains likely cause
- Guardian blocks unsafe releases
- Oversight audits the workflow

This gives a strong story for emergent coordination, even if the primary
training loop currently focuses on the Reliability Agent.

## Current Action Space

The training layer currently derives actions from the environment/task itself.

Key actions include:

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

## Current Reward Story

The reward logic should be presented around these behaviors:

Positive signals:

- useful evidence gathering
- correct root-cause identification
- meaningful mitigation
- service restoration
- correct incident closure

Negative signals:

- wasted actions
- redundant inspection loops
- harmful mitigation
- premature closure
- restored-but-not-resolved endings

Key outcome metrics already tracked in training:

- `env_reward`
- `train_reward`
- `root_cause_rate`
- `restore_rate`
- `success_rate`
- `closure_gap_rate`

This is strong hackathon material because it shows improvement beyond raw reward.

## Minimum Hackathon Deliverables

These must be complete.

### 1. OpenEnv-Compliant Environment

Must clearly show:

- environment class
- reset/step lifecycle
- actions
- reward behavior

### 2. Minimal Training Script

Already exists in:

- [rl_training.py](C:/My%20Projects/AgenEnv/rl_training.py)

For the hackathon, we should present:

- random baseline
- epsilon-greedy training
- reward/result summaries

If time allows, we can add a clean Colab-focused wrapper later.

### 3. Reward Improvement Evidence

We need at least:

- baseline run
- trained run
- before/after metrics
- one or two example successful trajectories

### 4. Hosted Environment

We should package the environment/story so it can be shown on:

- Hugging Face Spaces

Even if the full product UI is not fully hosted there, the environment-facing
demo must be easy to explain and run.

### 5. Storytelling Asset

Need one of:

- short Hugging Face blog
- short YouTube video under 2 minutes

The story should be:

1. software incidents are hard for LLMs
2. they require long-horizon evidence gathering
3. OpenIncident X simulates this realistically
4. the agent improves with training

## What To Demo

The strongest live demo is:

1. show the environment/problem
2. show the action space
3. show a baseline policy
4. show training output / reward curve
5. show an improved run
6. show the dashboard as the operational visualization layer

### Demo Narrative

Recommended demo flow:

1. "This is a realistic production incident world."
2. "The agent cannot see everything at once."
3. "It must inspect logs/metrics/traces and choose mitigation."
4. "Random behavior performs poorly."
5. "After training, the agent improves on restoration and closure."
6. "The surrounding multi-agent system shows how this fits into real software operations."

## What We Should Deprioritize For The Hackathon

For the next 24 hours, these are secondary:

- pixel-perfect frontend polish
- every dashboard tab being perfect
- full autonomy for all agents
- production-grade auth expansion
- every external integration
- generic support for every possible project type

If a task does not improve:

- environment clarity
- training clarity
- reward evidence
- OpenEnv compliance
- demo storytelling

then it is lower priority for the hackathon.

## Hackathon Submission Scope

### Must Feel Finished

- `ProductionIncidentEnv`
- `rl_training.py`
- reward/result reporting
- one clear submission story
- one clear demo flow
- one clear architecture explanation

### Nice To Have

- cleaner results export
- Hugging Face Space wrapper
- Colab notebook
- polished reward plots
- better successful-trajectory examples

### Can Wait Until After Submission

- training every other agent
- full cross-project generalization
- deeper UI polish
- richer live connectors
- large-scale route/selector intelligence

## Final Submission Positioning

If we need a sharp final description, use this:

> OpenIncident X is an OpenEnv-compatible multi-agent professional-operations
> environment for training LLMs on long-horizon incident response. Agents must
> gather evidence under partial observability, choose recovery actions, and
> resolve incidents correctly. We train a Reliability Agent inside this world
> and use surrounding specialist agents to model realistic software-operations
> workflows.

## Bottom Line

For the hackathon, success is:

- one sharp environment
- one believable training target
- one measurable improvement story
- one clean demo

That is enough to make OpenIncident X feel ambitious, coherent, and real.
