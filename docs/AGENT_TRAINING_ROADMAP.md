# OpenIncident X Agent Training Roadmap

## Purpose

This document explains how the remaining agents should be improved and trained.

The key design rule is simple:

- not every agent should be trained with Reinforcement Learning
- only agents with a sequential action policy and meaningful reward loop are strong RL candidates
- the other agents should first improve through better tooling, better datasets, and supervised evaluation

## Executive Summary

Right now, the best true RL target is:

- `Reliability Agent`

Why:

- it operates inside `ProductionIncidentEnv`
- it has a real action space
- it has a reward loop
- it makes sequential decisions
- it has clear success and failure conditions

The other agents should **not** be forced into RL first.

They should be improved in this order:

1. `Planner Agent` via routing datasets and offline evaluation
2. `Environment Agent` via tooling, fixtures, and framework-detection coverage
3. `Frontend Test Agent` via executed browser-story datasets
4. `API Test Agent` via structured API validation datasets
5. `Observability Agent` via signal-correlation datasets
6. `Triage Agent` via summary-quality evaluation
7. `Guardian Agent` via release-decision datasets
8. `Oversight Agent` via audit and reviewer datasets

## Training Strategy By Agent

### 1. Planner Agent

Recommended strategy:

- `Hybrid`

Why:

- planner quality depends on correct decomposition
- it needs accurate domain classification
- it needs good handoff decisions
- this is mainly a routing-quality problem, not a reward-maximization problem

Best first training path:

- collect stories and test cases
- store planner domain predictions
- store assigned agent decisions
- compare them with downstream execution outcomes
- learn from operator corrections

Current project support:

- `GET /projects/{project_id}/planner-training-dataset`
- this exposes planner decisions together with final story outcomes so we can evaluate routing quality offline

What to train later:

- smarter routing
- better execution priority
- better next-step recommendations

### 2. Environment Agent

Recommended strategy:

- `Heuristic + Tooling`

Why:

- this agent is mostly about workspace pull, framework discovery, route discovery, and command inference
- better deterministic tooling is stronger than RL here

Best first training path:

- build repository fixtures across many frameworks
- test framework detection accuracy
- test inferred install/test command quality
- evaluate route discovery against known repos

What to train later:

- optional hybrid ranking for best guessed commands or working directories

### 3. Frontend Test Agent

Recommended strategy:

- `Supervised Evaluation`

Why:

- frontend quality depends on mapping a story to route, selector, text, and browser checks
- this is best improved with executed examples and browser traces

Best first training path:

- save story input
- save inferred route and selector
- save browser output and screenshot
- save pass/fail outcome

Current project support:

- `GET /projects/{project_id}/frontend-training-dataset`
- this exposes inferred frontend plan signals together with browser execution outcomes

What to train later:

- better route inference
- better selector inference
- better expected-state reasoning

### 4. API Test Agent

Recommended strategy:

- `Supervised Evaluation`

Why:

- API testing is about translating requirements into endpoints, methods, payloads, auth, and expected responses
- this is mainly a structured reasoning and validation problem

Best first training path:

- save API stories and testcase inputs
- save expected method/path/status
- save actual execution outputs
- compare failures and false negatives

Current project support:

- `GET /projects/{project_id}/api-training-dataset`
- this exposes expected API intent together with actual endpoint execution outcomes

What to train later:

- better endpoint inference
- better auth handling
- better contract validation

### 5. Database Agent

Recommended strategy:

- `Hybrid`

Why:

- database reasoning needs schema understanding, migration logic, and data integrity checks
- this needs fixtures and structure before any serious policy learning

Best first training path:

- build schema and migration scenarios
- build data consistency bug cases
- store DB-related story outcomes

What to train later:

- remediation suggestion ranking
- migration risk reasoning

### 6. Observability Agent

Recommended strategy:

- `Hybrid`

Why:

- observability is about selecting useful signals from logs, metrics, and traces
- this is part extraction, part ranking, part explanation

Best first training path:

- store evidence bundles from incidents
- store final root causes
- learn which signals were useful

Current project support:

- `GET /projects/{project_id}/observability-training-dataset`
- this exposes validation signals with the surrounding log, metric, and active-incident context captured at check time

What to train later:

- stronger evidence correlation
- smarter signal prioritization

### 7. Reliability Agent

Recommended strategy:

- `Reinforcement Learning`

Why:

- it already has a real environment
- it already has actions
- it already has rewards
- it already has termination conditions

Current state:

- this is the first proper RL target in OpenIncident X
- `rl_training.py` is already training this agent

What to improve next:

- better reward alignment
- better trajectory export
- stronger state representation
- model-backed policies later

### 8. Triage Agent

Recommended strategy:

- `Supervised Evaluation`

Why:

- triage is about summary quality, evidence quality, and recommendation quality
- this is not a strong first RL problem

Best first training path:

- collect incident evidence bundles
- collect human-approved triage summaries
- compare recommendation usefulness

Current project support:

- `GET /projects/{project_id}/triage-training-dataset`
- this exposes historical triage summaries with confidence, evidence volume, recommended actions, and incident state context

What to train later:

- confidence calibration
- better explanation ranking

### 9. Guardian Agent

Recommended strategy:

- `Hybrid`

Why:

- guardian is a release decision gate
- it should first learn from known blocked/pass outcomes
- later it can become a stronger decision policy

Best first training path:

- store predeploy outcomes
- store incident state at release time
- store human override decisions

Current project support:

- `GET /projects/{project_id}/guardian-training-dataset`
- this exposes historical Guardian gate decisions together with open-incident and latest-check context

What to train later:

- calibrated risk thresholds
- better edge-case handling

### 10. Oversight Agent

Recommended strategy:

- `Supervised Evaluation`

Why:

- oversight is basically an auditor or reviewer
- it should learn to identify weak decisions and false confidence

Best first training path:

- collect agent traces
- collect final outcomes
- label good and bad decisions

Current project support:

- `GET /projects/{project_id}/oversight-training-dataset`
- this exposes audit-oriented handoffs to Oversight together with linked story or run outcomes

What to train later:

- decision auditing
- false-positive reduction

## What We Should Do Next

The right order is:

1. Keep RL work focused on `Reliability Agent`
2. Start logging structured decisions for the other agents
3. Build offline evaluation datasets for Planner, Frontend, API, Triage, and Guardian
4. Improve Environment Agent with stronger tooling and repo fixtures
5. Promote agents to hybrid or RL only after they have measurable evaluation benchmarks

## Bottom Line

The remaining agents should absolutely be improved and eventually trained.

But the correct approach is:

- `Reliability Agent` -> RL first
- `Planner / Frontend / API / Triage / Guardian / Oversight` -> evaluation-first
- `Environment Agent` -> tooling-first
- `Database / Observability` -> hybrid after better structure exists

That is the path that makes OpenIncident X stronger instead of just more complicated.
