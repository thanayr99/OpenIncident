# Environment Agent

## Purpose

The Environment Agent is responsible for preparing project execution context.

Its job is to:

- pull the repository
- discover framework and app structure
- prepare the testing workspace
- infer execution context for downstream agents
- connect project context to validation workflows

This agent is the operational setup layer that makes the rest of the system possible.

## Where It Sits In The Flow

The Environment Agent acts early, after the Planner and before deep validation.

Typical flow:

1. User creates/selects a project
2. Planner decides what kinds of checks are needed
3. `Environment Agent` prepares repo and workspace context
4. Frontend/API/Database agents use that context for execution

## Core Responsibilities

The Environment Agent is responsible for:

- pulling GitHub repositories
- configuring project test environments
- discovering app root and likely framework
- discovering candidate frontend routes
- exposing workspace and runtime context to other agents

## Inputs

The Environment Agent should consume:

- repository URL
- branch information
- optional deployed URL
- install command
- test command
- workdir hints
- project metadata

In the current product these inputs come from:

- project creation
- testing environment configuration
- GitHub/test-environment setup
- frontend discovery requests

## Outputs

The Environment Agent should produce:

- pulled workspace path
- detected framework
- candidate routes
- app root hints
- install/test environment status
- execution context for downstream agents

## What It Does Today

Today this agent is already one of the most practical infrastructure agents.

It currently supports:

- repository-linked test environments
- workspace pull/update
- install/test command execution
- frontend discovery
- route and framework discovery

This makes it one of the most operationally real agents in the project today.

## Current Product Mapping

This agent maps most directly to:

- test-environment configuration APIs
- test-environment execution APIs
- GitHub workspace pull flow
- frontend discovery endpoints

It is surfaced through:

- project testing environment configuration
- workspace pull results
- discovered frontend route outputs
- command-center setup flow

## Success Criteria

The Environment Agent should eventually be judged on:

1. `workspace_setup_success`
How often it correctly prepares project execution context

2. `framework_detection_quality`
How accurately it identifies the project's stack

3. `route_discovery_quality`
How useful the discovered frontend routes are

4. `downstream_enablement_quality`
How much it improves other agents' ability to execute correctly

5. `repo_generalization_quality`
How well it handles different project structures

## Known Failure Modes

Current likely failure modes:

- wrong framework inference
- wrong workdir assumptions
- incomplete route discovery
- weak handling of unusual repo layouts
- setup success without enough useful context for downstream agents

## Dashboard Representation

On the frontend, the Environment Agent should appear as:

- the setup and workspace-preparation agent
- the source of repo and route-discovery context
- the owner of test-environment state

Recommended dashboard signals for this agent:

- workspace status
- repo sync status
- framework detected
- routes discovered
- test-environment last run

## Capabilities It Should Have When Mature

The mature Environment Agent should be able to:

- detect framework and project shape robustly
- infer test commands more intelligently
- prepare frontend and backend execution contexts
- discover likely routes and key app surfaces
- support a wide variety of repositories with minimal manual hints

## What It Should Not Do

The Environment Agent should not:

- classify stories initially
- perform the final browser/API assertions itself
- decide incident remediation
- decide release approval
- act as final auditor

Those belong to:

- Planner
- Frontend/API Test Agents
- Reliability Agent
- Guardian
- Oversight

## RL / Training Possibility

The Environment Agent is a future candidate for setup-policy improvement, but it is not a first RL target.

A future Environment-Agent training setup could use:

- state:
  - repo structure
  - config files
  - prior setup attempts
  - project metadata
- actions:
  - choose workdir
  - choose install/test command
  - choose route candidates
  - choose framework hypothesis
- reward:
  - correct setup
  - better downstream validation success
  - less manual intervention

This is a setup and discovery policy problem, not the current Reliability-Agent incident-response loop.

## Refinement Roadmap

### Phase 1

- improve framework detection
- improve route discovery
- improve test-environment clarity in the dashboard

### Phase 2

- support more repo layouts and stacks
- improve automatic command inference
- improve downstream handoff quality

### Phase 3

- collect setup/deployment trajectories
- train discovery and setup policies
- benchmark generalization across diverse projects

## Bottom Line

The Environment Agent is the setup and workspace-preparation specialist in OpenIncident X.

It should answer:

- did we pull and prepare the project correctly?
- what framework and routes does this repo likely have?
- what context do the downstream agents need?

It is one of the key infrastructure agents that makes the rest of the system work reliably.
