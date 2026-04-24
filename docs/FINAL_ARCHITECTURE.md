# OpenIncident X Final Architecture

## Product Definition

OpenIncident X is a deployable, OpenEnv-compatible multi-agent enterprise operations environment.
It combines:

- incident detection and triage
- user-story driven validation
- browser, API, and health checks
- future code, logs, metrics, and deployment context
- reward-based training and evaluation

The system should work both as:

1. a live command-center application
2. a training environment for agent improvement

## Core Layers

### 1. Environment Layer

This is the OpenEnv-facing layer.

- `reset()`
- `step()`
- `state()`
- reward logic
- scenario state transitions

This is where the training loop interacts with the world.

### 2. Incident Control Plane

This is the backend orchestration layer.

Responsibilities:

- manage projects
- manage sessions
- manage incident runs
- manage story runs
- manage signal snapshots
- manage story reports

### 3. Signal Layer

Signal sources represent how the environment sees the outside world.

Current:

- health checks
- API checks
- browser checks with Playwright

Next:

- GitHub repository inspection
- logs ingestion
- metrics ingestion
- deploy/change context

### 4. Agent Layer

This is the reasoning and execution layer.

Planned roles:

- Monitor Agent
- Planner Agent
- Frontend Test Agent
- API Test Agent
- Database Analyst Agent
- Resolver Agent
- Oversight Agent

### 5. Presentation Layer

This is the command-center UI.

Responsibilities:

- show project health
- show incident feed
- show user-story progress
- show evidence and triage
- show reward and evaluation summaries

## Main Entities

### Project

A connected application or service.

Fields:

- name
- base URL
- repository URL
- health path
- monitor config

### Incident Run

One active or historical incident lifecycle.

### Session

The active stateful investigation context for a run.

### User Story

A project requirement submitted by the user.

Each story contains:

- title
- description
- acceptance criteria
- tags
- execution hints
- current status
- analysis
- latest result

### Story Report

Aggregated project-level story completion report:

- total stories
- completed
- failed
- blocked
- pending
- progress percent

## User Story Workflow

1. User submits stories for a project.
2. Planner analyzes and classifies them.
3. Story is assigned to a domain and agent role.
4. Appropriate validation is executed.
5. Story result is recorded.
6. Project report is updated.
7. Failed stories can later open incidents automatically.

## Scenario Families

### Scenario 1: Frontend Regression
- missing or broken rendered content

### Scenario 2: API Failure
- invalid endpoint status or contract

### Scenario 3: Recovery Verification
- issue looks fixed but must be verified

### Scenario 4: False Positive vs Real Incident
- conflicting signals must be interpreted carefully

### Scenario 5: Story-to-Test Validation
- user stories must be classified, executed, and reported

## Reward Directions

Positive reward:

- correct detection
- useful evidence gathering
- correct triage
- correct story classification
- correct test routing
- verified recovery
- proper closure

Negative reward:

- wrong diagnosis
- wrong story routing
- redundant actions
- premature closure
- false pass / false fail

## Build Order

### Phase 1: Stable Backbone

- projects
- sessions
- incidents
- browser/API/health checks
- dashboard

### Phase 2: User Story System

- story models
- story analysis
- story execution
- project reports

### Phase 3: Intelligence and Evidence

- GitHub inspection
- logs ingestion
- metrics
- deploy context

### Phase 4: Training and Demo

- OpenEnv alignment
- minimal TRL/Unsloth script
- reward curves
- final command-center polish

## Current Build Priorities

1. finish the user-story workflow foundation
2. connect GitHub inspection for `inspect_code`
3. add log ingestion
4. add metrics snapshot support
5. connect story failures to incident creation
6. improve dashboard for story and incident command-center views
