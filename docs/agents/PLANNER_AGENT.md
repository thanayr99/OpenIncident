# Planner Agent

## Purpose

The Planner Agent is the orchestration brain at the start of the OpenIncident X workflow.

Its job is to:

- understand the project context
- read user stories or formal test cases
- classify work by domain
- decide execution order
- assign the right work to the right downstream agent

If the Planner is weak, every other agent becomes reactive, duplicated, or noisy.

## Where It Sits In The Flow

The Planner Agent is the first reasoning layer after the user provides project inputs.

Typical flow:

1. User signs in
2. User creates/selects project
3. User provides:
   - repository URL
   - optional deployed URL
   - stories or test cases
   - optional logs
4. `Planner Agent` analyzes the work
5. Planner hands off to:
   - Environment Agent
   - Frontend Test Agent
   - API Test Agent
   - Database Agent
   - Observability Agent

## Core Responsibilities

The Planner Agent is responsible for:

- reading incoming stories and test cases
- extracting intent and acceptance criteria
- identifying the relevant domain:
  - frontend
  - API
  - database
  - auth
  - deployment
  - observability
- deciding what needs to run first
- building a handoff plan for downstream agents
- avoiding duplicate or unnecessary execution

## Inputs

The Planner Agent should consume:

- project metadata
- repository URL
- deployed/base URL
- imported user stories
- imported QA-style test cases
- project health summary
- previously known incidents or recent runs

In the current product, these inputs come from:

- project creation
- bulk story/test-case import
- saved project state
- command-center summary APIs

## Outputs

The Planner Agent should produce:

- story classification
- recommended domain per item
- recommended test type per item
- execution order
- downstream agent assignment
- planning notes for the dashboard

The Planner should not run deep validation itself.
Its output should be a work plan, not the browser/API/database execution result.

## What It Does Today

Today the Planner Agent exists mostly as workflow intelligence through:

- story analysis and normalization
- domain inference
- test-type inference
- coordination traces
- agent handoff/event recording

It is currently more rule-based than learned.

## Current Product Mapping

The Planner is represented by the agent role:

- `planner`

It currently contributes to:

- story segregation
- routing work toward frontend/API/database-type validation
- project-level coordination state shown in the dashboard

## Decision Rules

The Planner should use rules like:

- if a story references visible UI, text, buttons, or user navigation:
  - route to Frontend Test Agent
- if a story references endpoint behavior, status codes, auth, or payloads:
  - route to API Test Agent
- if a story references schema, persistence, migrations, or stored correctness:
  - route to Database Agent
- if a story references logs, runtime failures, or operational evidence:
  - route to Observability Agent
- if validation fails and impact is operational:
  - route to Reliability Agent

## Success Criteria

The Planner Agent should eventually be judged on:

1. `classification_accuracy`
How often it assigns the correct domain

2. `routing_accuracy`
How often it sends work to the right agent

3. `execution_efficiency`
How often it reduces unnecessary checks

4. `coverage_quality`
How well imported stories are converted into executable validations

5. `handoff_quality`
How useful its work packets are for downstream agents

## Known Failure Modes

Current likely failure modes:

- assigning frontend work to API testing
- classifying broad business stories too vaguely
- triggering too many redundant checks
- failing to separate multi-domain stories into smaller tasks
- ignoring dependencies between tasks

## Dashboard Representation

On the frontend, the Planner Agent should appear as:

- the first coordinator in the agent chain
- the owner of work routing
- the source of execution plans

Recommended dashboard signals for this agent:

- number of stories analyzed
- domain breakdown
- assigned agents
- blocked/unclassified stories
- next recommended execution path

## Capabilities It Should Have When Mature

The mature Planner Agent should be able to:

- decompose complex stories into smaller executable tasks
- detect cross-domain dependencies
- prioritize validation order intelligently
- route work with low ambiguity
- react to project context such as framework, repo shape, and previous failures
- re-plan dynamically when incidents open

## What It Should Not Do

The Planner Agent should not:

- run Playwright checks directly
- execute API calls directly
- own incident mitigation
- close incidents
- act as the final release gate

Those belong to:

- Frontend Test Agent
- API Test Agent
- Reliability Agent
- Guardian

## RL / Training Possibility

The Planner Agent is a strong future RL or imitation-learning candidate, but it is not the first one to train.

Why:

- its action space is more abstract than the Reliability Agent
- its reward is less direct
- it needs labeled routing quality and outcome feedback

A future Planner training setup could use:

- state:
  - project context
  - story text
  - historical outcomes
- actions:
  - classify domain
  - assign agent
  - assign priority
  - split story
- reward:
  - downstream success
  - fewer redundant checks
  - better coverage

## Refinement Roadmap

### Phase 1

- improve story/test-case parsing quality
- improve domain inference
- improve routing transparency in the dashboard

### Phase 2

- add multi-domain story decomposition
- add dependency-aware scheduling
- add planner confidence scores

### Phase 3

- collect planner trajectories
- train a routing policy
- benchmark routing quality against downstream execution success

## Bottom Line

The Planner Agent is the system's orchestration brain.

It should decide:

- what the work is
- which domain it belongs to
- which agent should handle it
- what should happen first

It is one of the most important agents in OpenIncident X, even though it is not the first RL-trained one.
