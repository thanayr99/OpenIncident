# Reliability Agent

## Purpose

The Reliability Agent is the incident-response decision maker inside OpenIncident X.

Its job is to:

- investigate failing production signals
- identify the likely root cause
- choose remediation actions
- restore service safely
- close the incident only when the system is actually healthy again

This is the first agent in the project that now has a concrete RL-style training loop attached to it.

## Where It Sits In The Flow

The Reliability Agent acts after validation and observability evidence exist.

Typical flow:

1. User creates project
2. Planner classifies work
3. Frontend/API/other checks run
4. Logs/metrics/traces are attached
5. Incident opens
6. `Reliability Agent` investigates and mitigates
7. Triage explains the result
8. Guardian/Oversight decide whether the project is safe

## Core Responsibilities

The Reliability Agent is responsible for:

- reading incident state
- inspecting logs, metrics, traces, deploys, config, and code
- identifying root cause
- deciding whether to:
  - apply a fix
  - rollback deploy
  - restart service
  - scale service
  - add monitoring
  - resolve the incident
- avoiding unsafe or premature closure

## Current Environment Mapping

This agent maps directly to the `ProductionIncidentEnv` action space in:

- [environment.py](/C:/My%20Projects/AgenEnv/server/environment.py)

Current supported actions:

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

This is why the current RL trainer is for the Reliability Agent and not for the Planner or Frontend/API test agents.

## Inputs

The Reliability Agent should consume:

- incident summary
- service name
- severity
- user impact
- logs
- metrics
- traces
- recent deploys
- config snapshot
- code snippet
- check results
- prior action history

In the real product workflow, these inputs come from:

- failing browser/API/health checks
- story execution failures
- log connectors
- test-environment runs
- triage state

## Outputs

The Reliability Agent should produce:

- the next action to take
- a mitigation path
- updated incident state
- whether service is restored
- whether monitoring was added
- whether the incident is ready to be resolved

It should not merely produce a text summary.
It should produce operational decisions.

## What It Does Today

Today the Reliability Agent is partly implemented through:

- workflow orchestration in the application layer
- incident state transitions in the environment
- the RL add-on trainer in:
  - [rl_training.py](/C:/My%20Projects/AgenEnv/rl_training.py)

The trainer currently supports:

- random baseline
- epsilon-greedy Q-learning baseline
- optional HuggingFace policy adapter

The trainer now treats this as a Reliability-Agent policy problem.

## Training Setup

### Current training target

The current RL policy is learning:

- what to inspect first
- when root cause is likely known
- when mitigation should happen
- when service is truly restored
- when incident closure is appropriate

### Important note

The trainer is not yet teaching the full product workflow.
It is teaching the incident-decision behavior of the Reliability Agent inside the OpenEnv environment.

That means:

- `Planner Agent` training is separate
- `Frontend/API testing` training is separate
- `Guardian/Oversight` training is separate

## Reward Logic

The environment already gives rewards for:

- useful actions
- confirmed diagnosis
- service restoration
- monitoring addition
- reliability score

The training layer now adds stronger shaping for Reliability-Agent quality:

- bonus when root cause becomes confirmed
- bonus when mitigation is applied
- bonus when service is restored
- bonus when monitoring is added
- terminal bonus for real resolution
- penalty for unresolved endings
- penalty for restoring service but failing to close the incident
- penalty for `do_nothing`
- penalty when the latest action produced an error

This is important because the earlier reward signal could give high scores for partial progress without actual incident closure.

## Success Criteria

The Reliability Agent should eventually be judged on:

1. `root_cause_rate`
How often it correctly identifies the root cause

2. `restore_rate`
How often it restores service

3. `success_rate`
How often it fully resolves the incident

4. `closure_gap_rate`
How often it restores service but forgets or fails to properly resolve the incident

5. `step_efficiency`
How efficiently it reaches the correct result

## Known Failure Modes

Current likely failure modes:

- over-inspecting without acting
- partial mitigation with no closure
- harmful mitigation choices
- random success from weak exploration
- reward chasing without full resolution
- over-trusting partial recovery

In the latest runs, one visible issue was:

- service sometimes became restored
- but the incident remained unresolved

This is why closure-gap tracking now exists in the trainer.

## Dashboard Representation

On the frontend, the Reliability Agent should appear as:

- the active incident-response operator
- the owner of mitigation decisions
- the agent that changes state from:
  - investigating
  - mitigated
  - resolved

Recommended dashboard signals for this agent:

- current incident state
- current suspected root cause
- chosen remediation path
- restoration status
- closure readiness
- action timeline

## Capabilities It Should Have When Mature

The mature Reliability Agent should be able to:

- rank evidence sources
- choose the best next inspection
- avoid unnecessary actions
- distinguish symptom fixes from root-cause fixes
- apply safe remediation
- know when recovery is partial versus complete
- add preventative monitoring
- close incidents only when justified

## What It Should Not Do

The Reliability Agent should not:

- classify user stories at the start of the workflow
- own repo discovery
- own browser/API execution itself
- act as the release gate
- act as final auditor

Those belong to:

- Planner
- Environment Agent
- Frontend/API Test Agents
- Guardian
- Oversight

## Refinement Roadmap

### Phase 1

- stabilize reward shaping
- reduce closure-gap behavior
- log successful trajectories
- compare random vs epsilon vs HF more clearly

### Phase 2

- export trajectories for offline training
- add action masking or action ranking
- improve state encoding
- add more realistic incident families

### Phase 3

- train a stronger model-backed policy
- benchmark across easy/medium/hard tasks
- connect learned behavior back into the product workflow

## Recommended Next Technical Steps

1. Add trajectory export:
   - state
   - action
   - reward
   - next_state
   - done

2. Add action-mask logic so clearly invalid actions are discouraged earlier

3. Add evaluation reports per task difficulty

4. Add success-sequence analysis so we know what action chains actually work

## Bottom Line

The Reliability Agent is the best first RL target in OpenIncident X because:

- it has a clear action space
- it has meaningful rewards
- it has measurable success/failure
- it sits at the core of incident handling

Right now, the RL work in this project should be understood as:

- `training the Reliability Agent's incident-decision policy`

That is the correct starting point before training other specialized agents.
