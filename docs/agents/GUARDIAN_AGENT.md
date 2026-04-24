# Guardian Agent

## Purpose

The Guardian Agent is the release-safety gatekeeper in OpenIncident X.

Its job is to:

- decide whether a project is safe to pass
- block unsafe progression when validation fails
- ensure unresolved incidents stop release readiness
- enforce minimum operational quality before allowing confidence

This agent protects the system from false confidence.

## Where It Sits In The Flow

The Guardian Agent acts near the end of the operational flow, after evidence and validation results already exist.

Typical flow:

1. Stories/test cases are analyzed
2. Frontend/API/database/observability work runs
3. Incidents and triage are generated if needed
4. `Guardian Agent` checks whether release or readiness should be blocked
5. Oversight may audit the Guardian's decision

## Core Responsibilities

The Guardian Agent is responsible for:

- evaluating predeploy or readiness state
- blocking release when critical checks fail
- blocking release when incidents remain open
- requiring key validation conditions to pass
- exposing a clear ready/not-ready decision

## Inputs

The Guardian Agent should consume:

- story execution results
- browser/API/health check results
- open incident state
- triage output
- reliability state
- project summary
- testing environment results

In the current product these inputs come from:

- project predeploy/testing flows
- incident state
- project summary endpoints
- command-center checks

## Outputs

The Guardian Agent should produce:

- release or readiness decision
- blocked/not-blocked state
- gate reasons
- missing conditions
- recommended remediation before passing

## What It Does Today

Today the Guardian exists mainly as a release-gating concept plus workflow logic.

It currently contributes through:

- predeploy-style status evaluation
- blocked/ready interpretations in the dashboard
- story and incident pass/fail influence on readiness

It is still largely rule-based, which is appropriate for now.

## Current Product Mapping

This agent maps most directly to the agent role:

- `test_env_guardian`

And conceptually to:

- predeploy validation
- readiness gating
- release safety status in the command center

## Success Criteria

The Guardian Agent should eventually be judged on:

1. `unsafe_release_block_rate`
How often it correctly blocks unsafe release states

2. `false_block_rate`
How often it blocks when the project is actually acceptable

3. `gate_reason_quality`
How clear and actionable its block reasons are

4. `incident_awareness_quality`
How well it incorporates active incidents into release decisions

5. `trustworthiness`
How consistently teams can rely on its gate outcome

## Known Failure Modes

Current likely failure modes:

- allowing a project through with unresolved critical incidents
- over-blocking minor issues
- weak explanation of why the gate failed
- depending too heavily on incomplete evidence
- failing to differentiate partial recovery from true readiness

## Dashboard Representation

On the frontend, the Guardian Agent should appear as:

- the release gate
- the pass/block decision owner
- the source of readiness explanations

Recommended dashboard signals for this agent:

- gate status
- blocked conditions
- passed conditions
- open incidents affecting readiness
- release readiness summary

## Capabilities It Should Have When Mature

The mature Guardian Agent should be able to:

- combine validation, incidents, and triage into one decision
- distinguish critical blockers from minor warnings
- justify release decisions clearly
- adapt gate strictness to risk level
- detect unsafe partial recovery states

## What It Should Not Do

The Guardian Agent should not:

- classify stories initially
- run browser or API checks directly
- own root-cause analysis
- perform final auditing of all agents

Those belong to:

- Planner
- Frontend/API Test Agents
- Reliability/Triage
- Oversight

## RL / Training Possibility

The Guardian Agent is a future candidate for policy improvement, but rule-based behavior is the right default first.

A future Guardian training setup could use:

- state:
  - check results
  - incident state
  - triage confidence
  - story outcomes
- actions:
  - block
  - allow
  - require more evidence
  - mark warning-only
- reward:
  - fewer unsafe approvals
  - fewer false blocks
  - strong release trust

This is closer to decision-theory and governance learning than the current Reliability-Agent RL loop.

## Refinement Roadmap

### Phase 1

- improve gate transparency
- improve blocked-condition reporting
- improve linkage between incidents and readiness

### Phase 2

- add richer gate policies by severity/risk
- reduce false blocks
- improve explanation quality

### Phase 3

- collect gate-decision trajectories
- train or benchmark readiness decisions
- integrate deeper with Oversight

## Bottom Line

The Guardian Agent is the release-safety gatekeeper in OpenIncident X.

It should answer:

- is this project actually safe to pass?
- are there unresolved blockers?
- do we have enough evidence to trust the current state?

It is one of the key trust-building agents in the whole system.
