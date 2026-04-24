# OpenIncident X Agent System Overview

## Purpose

This document explains:

1. The correct flow of agents in OpenIncident X
2. What each agent does
3. How the agents currently run in this codebase
4. Where RL and OpenEnv exist today
5. What is already functional versus what is still a planned upgrade
6. What should happen next before refining each agent separately

## Executive Summary

OpenIncident X currently combines two layers:

1. `Application layer`
   This is the product workflow for real projects:
   - user signs in
   - creates project
   - links GitHub repo
   - optionally links deployed URL
   - imports user stories / test cases
   - runs health, browser, API, log, and test-environment checks
   - opens incidents
   - triages failures

2. `Environment layer`
   This is the OpenEnv-style incident simulation:
   - a stateful incident environment
   - a defined action space
   - a reward function
   - difficulty-based tasks (`easy`, `medium`, `hard`)
   - graders that score successful incident handling

Right now, the product agents are mostly orchestration and reasoning components backed by rules, heuristics, persistence, and workflow logic.

The true RL/OpenEnv part currently exists inside the `ProductionIncidentEnv` environment and graders, not as separately trained production agents yet.

That means:

- `Current system`: multi-agent application with an RL-style incident environment embedded inside it
- `Future system`: each major agent can become a more fully trained and independently evaluated capability

## Correct Agent Flow

The cleanest operational flow is:

1. `Operator/User`
2. `Planner Agent`
3. `Repository / Environment Agent`
4. `Frontend Test Agent`
5. `API Test Agent`
6. `Database Agent`
7. `Observability / Log Agent`
8. `Reliability Agent`
9. `Triage Agent`
10. `Guardian Agent`
11. `Oversight Agent`

## Why This Order Is Correct

### 1. Operator/User

The user provides:

- account information
- project name
- repository URL
- optional deployed URL
- user stories or formal test cases
- optional logs or log connector

The user should never manually orchestrate the inner reliability workflow.
Their job is only to provide project intent and evidence sources.

### 2. Planner Agent

This is the system entrypoint for reasoning.

The Planner should:

- read stories and test cases
- classify work by domain
- decide the primary execution order
- assign the work to the right downstream agent
- create the handoff plan

Without the Planner, every other agent becomes reactive and fragmented.

### 3. Repository / Environment Agent

This agent prepares execution context.

It should:

- pull the GitHub repository
- discover framework and app structure
- detect likely frontend routes
- infer API surfaces
- configure workspace/test environment
- expose repo context to the testing agents

This agent should run before deep validation because the other agents need repo/runtime context.

### 4. Frontend Test Agent

This agent owns browser-rendered validation.

It should:

- run Playwright checks
- validate visible text and selectors
- validate navigation and UI flows
- verify page-level user stories
- identify frontend regressions

### 5. API Test Agent

This agent owns service/API validation.

It should:

- run API endpoint checks
- validate status codes
- validate request/response behavior
- validate auth and contract assumptions
- identify backend/API failures

### 6. Database Agent

This agent owns data and persistence reasoning.

It should:

- reason about DB-related user stories
- inspect data assumptions
- validate persistence-related failures
- later support migrations, schema checks, data integrity checks

Today it is more of a reasoning role than a full DB execution engine.

### 7. Observability / Log Agent

This agent owns runtime evidence.

It should:

- pull logs
- summarize errors and warnings
- correlate signals with checks
- expose relevant evidence to triage and reliability
- later include metrics and traces more deeply

### 8. Reliability Agent

This is the incident-response coordinator.

It should:

- react to failed checks
- open or update incidents
- track active operational state
- combine user-story failure, browser/API evidence, and logs
- manage incident lifecycle

### 9. Triage Agent

This agent creates diagnosis.

It should:

- summarize the incident
- infer likely root cause
- measure confidence
- list evidence
- suggest recommended actions

### 10. Guardian Agent

This is the release gate.

It should:

- block unsafe releases
- decide if predeploy validation passed
- ensure failed stories/incidents block progression
- only allow release-ready state when core validations pass

### 11. Oversight Agent

This is the auditing layer.

It should:

- review agent decisions
- identify false positives / weak conclusions
- verify closure quality
- reduce bad escalations or premature success claims

## Current Agent Roles In This Codebase

The current codebase already defines these roles:

- `planner`
- `frontend_tester`
- `api_tester`
- `database_analyst`
- `reliability_analyst`
- `test_env_guardian`
- `oversight`

These are stored in the backend and surfaced in the dashboard through:

- agent roster
- coordination trace
- conversation trace
- event history

Important: these are currently workflow agents, not independently trained policies.

## How The Agents Are Running Today

Today the agents run through:

1. backend orchestration logic
2. story analysis/routing
3. validation execution
4. event + handoff recording
5. dashboard state rendering

### They are currently powered by:

- deterministic routing rules
- story/domain inference
- repo inspection logic
- browser/API checks
- incident creation logic
- triage summarization
- persistent project state in Neon/Postgres

### They are not yet:

- independently fine-tuned RL agents
- separately trained policies with dedicated reward loops
- multi-agent self-play learners

So today:

- `Agent behavior = workflow intelligence + stateful orchestration`
- `RL/OpenEnv = incident environment and grader loop`

## Where OpenEnv / RL Exists Right Now

The RL-like environment is the `ProductionIncidentEnv` in:

- [server/environment.py](/C:/My%20Projects/AgenEnv/server/environment.py)

### This environment provides:

- a state (`IncidentObservation`)
- a set of actions (`IncidentAction`)
- hidden and revealed evidence
- a transition function through `step(...)`
- a reward function through `_compose_reward(...)`
- terminal conditions like resolution or max steps

### Current supported actions

- inspect logs
- inspect metrics
- inspect traces
- inspect deploys
- inspect config
- inspect code
- identify root cause
- apply fix
- rollback deploy
- restart service
- scale service
- add monitor
- resolve incident
- do nothing

### Current RL-style tasks

The environment currently supports:

- `easy`
- `medium`
- `hard`

These tasks are drawn from the task registry and represent incident-response scenarios with different complexity.

## What The Reward Model Is

The reward currently combines:

- immediate action reward
- passed checks
- failed checks penalty
- root cause confirmation
- service restoration
- monitoring addition
- reliability score

This means the environment rewards:

- correct diagnosis
- effective remediation
- safe incident closure

And penalizes:

- wrong diagnosis
- harmful or irrelevant actions
- unresolved incidents

## What The Graders Are

The graders are explicit scoring functions for environment outcomes.

For example:

- [grader_hard.py](/C:/My%20Projects/AgenEnv/graders/grader_hard.py)

The hard grader currently scores based on:

- root cause confirmed
- service restored
- mitigation applied
- monitoring added
- step efficiency

This is the clearest current “reward/evaluation” layer in the repo.

## So What Is The RL Here Exactly?

The RL here is not yet “every agent is RL-trained.”

The RL here is:

1. an environment with state, actions, and rewards
2. a benchmark/evaluation setup for agent behavior
3. a structure that can be used for post-training or policy improvement

In other words:

- `OpenIncident X product agents` are the application workflow
- `ProductionIncidentEnv` is the RL/OpenEnv training/evaluation substrate

This is still valid for the hackathon because:

- there is a real environment
- there is a real action space
- there is reward logic
- there are graders
- there is measurable improvement potential

## How Training Would Work Conceptually

### Current state

Right now training is mostly implicit or future-facing:

- rules and logic decide behavior
- the environment can already evaluate behavior
- the grading functions can already score behavior

### Future training path

A proper training path would look like:

1. run trajectories in `ProductionIncidentEnv`
2. collect `(state, action, reward, done)` sequences
3. train or improve policy behavior
4. compare before/after grader scores
5. move the improved policy into one or more agents

### Two valid future directions

#### Option A: Train one central incident-response policy

This is simpler and faster.

- one policy handles incident tasks
- product agents remain orchestrators around it
- good for hackathon proof of improvement

#### Option B: Train agent-specialized policies

This is stronger long-term.

Examples:

- Planner policy
- Reliability policy
- Guardian policy
- Oversight policy

This is more ambitious and should come after the base workflow is stable.

## What Is Already Functional

The following are already functionally real:

- account/project workflow
- GitHub-linked workspace flow
- frontend discovery
- browser/API/health validation
- bulk story/test-case import
- incident opening from failures
- run triage generation
- Neon/Postgres persistence
- schema versioning
- database inspection
- RL-style incident environment
- graders

## What Is Still Transitional

The following are still transitional or incomplete:

- some complex simulator/session state still uses compatibility snapshot persistence
- agent behaviors are not separately trained
- database agent is not yet a deep execution agent
- observability agent is still logs-first and not fully traces/metrics-driven
- guardian and oversight are still largely rule-based
- multi-agent handoff is persisted and visualized, but not yet deeply autonomous

## Recommended Agent Refinement Order

This is the best sequence for making each agent fully functional:

### Phase 1: Orchestration Quality

1. Planner Agent
2. Repository / Environment Agent

Reason:
If planning and context preparation are weak, every downstream agent performs badly.

### Phase 2: Validation Quality

3. Frontend Test Agent
4. API Test Agent
5. Database Agent

Reason:
These determine whether user stories are checked correctly.

### Phase 3: Incident Quality

6. Observability Agent
7. Reliability Agent
8. Triage Agent

Reason:
These determine whether failures become actionable incidents instead of noisy output.

### Phase 4: Governance Quality

9. Guardian Agent
10. Oversight Agent

Reason:
These determine trust, release safety, and final system credibility.

## Recommended Next Documents

After this overview, create one document per agent:

1. `Planner Agent`
2. `Repository / Environment Agent`
3. `Frontend Test Agent`
4. `API Test Agent`
5. `Database Agent`
6. `Observability Agent`
7. `Reliability Agent`
8. `Triage Agent`
9. `Guardian Agent`
10. `Oversight Agent`

Each document should contain:

- purpose
- trigger conditions
- inputs
- outputs
- capabilities
- decision rules
- failure modes
- dashboard representation
- future RL/training possibility

## Final Mental Model

The simplest correct mental model is:

- `OpenIncident X` is a multi-agent reliability application
- `ProductionIncidentEnv` is the RL/OpenEnv environment inside it
- `graders` are the reward/evaluation layer
- `agents` are currently orchestration and execution roles
- the long-term vision is to make each important agent increasingly autonomous, capable, and measurable

This is the right base for refining each agent one by one.
