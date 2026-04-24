# OpenIncident X One-Day Hackathon Plan

## Goal

Finish the **hackathon submission version** of OpenIncident X in one focused day.

This plan is intentionally ruthless about priorities.

## Rule For Today

If a task does **not** directly improve one of these, it should wait:

- environment clarity
- training results
- reward evidence
- OpenEnv submission readiness
- demo storytelling

## Day Outcome

By the end of this plan, we should have:

1. a clear environment story
2. a stable training script run
3. saved metrics/results
4. a demo flow
5. a submission checklist

## Priority 1: Lock The Submission Story

### Done when

- [HACKATHON_BLUEPRINT.md](C:/My%20Projects/AgenEnv/docs/HACKATHON_BLUEPRINT.md) is the agreed source of truth
- we commit to:
  - primary theme: `Theme #3.1`
  - supporting themes: `#2`, `#1`
  - main trained agent: `Reliability Agent`
  - main environment: `ProductionIncidentEnv`

### Why this matters

Without this, the project will sprawl.

## Priority 2: Stabilize The Training Demo

### Required output

We need at least one reproducible run showing:

- random baseline
- epsilon-greedy improvement
- reward summary
- success-related metrics

### Required checks

- `python rl_training.py`
- `python rl_training.py --task-id medium --episodes 30 --policy epsilon`

### Nice-to-have checks

- `python rl_training.py --task-id hard --episodes 10 --policy hf --hf-model distilgpt2`

### Done when

- we have one clean result set we can show judges
- we can explain what improved

## Priority 3: Save Artifact Evidence

We should leave today with artifacts, not just terminal output.

### Must save

- rewards CSV
- reward plot
- summary metrics from one baseline and one trained run

### Suggested artifact folder

- `artifacts/`

### Done when

- we have files we can screenshot or show during the demo

## Priority 4: Package The Demo Flow

### We need a short demo that works even under time pressure

Recommended demo order:

1. explain the problem
2. show the environment and actions
3. run or show baseline results
4. show trained results
5. show the dashboard as the operational layer

### Done when

- we can explain the whole project in under 2 minutes

## Priority 5: Submission Checklist

### Must complete

- environment definition is clear
- training script is runnable
- reward logic is explainable
- results are saved
- one short blog or video outline exists
- Hugging Face Spaces hosting plan is defined

## Exact Work Order

### Block 1

Lock docs and scope:

1. confirm the main story
2. stop expanding low-priority product work

### Block 2

Run and record training:

1. baseline
2. trained run
3. save CSV
4. save plot

### Block 3

Polish the explanation layer:

1. concise environment explanation
2. concise reward explanation
3. concise demo script

### Block 4

Wrap submission assets:

1. Hugging Face / Colab plan
2. mini-blog or video outline

## What Not To Touch Today Unless Blocking

- large frontend redesigns
- broad cross-project support
- full training for every agent
- extra dashboards
- deep visual polish
- speculative integrations

## If Time Remains

Best extra upgrades in order:

1. cleaner training artifacts
2. cleaner reward plots
3. demo-specific dashboard cleanup
4. Hugging Face Spaces wrapper
5. Colab notebook wrapper

## Final Readiness Questions

Before we call the hackathon build ready, we should be able to answer:

1. What is the environment?
2. What is the action space?
3. What is the reward?
4. Which agent is trained?
5. What improved after training?
6. Why is this interesting and hard?
7. How does this connect to real-world software operations?

If those answers are strong, the submission is in good shape.
