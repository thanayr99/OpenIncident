# Database Agent

## Purpose

The Database Agent is responsible for reasoning about persistence, schema behavior, and data correctness inside OpenIncident X.

Its job is to:

- analyze database-related stories and failures
- inspect persistence assumptions
- identify schema or migration-related risks
- reason about data integrity problems
- contribute database evidence to incident handling

This agent is especially important when failures are not purely UI or API errors, but are caused by the data layer underneath them.

## Where It Sits In The Flow

The Database Agent acts after:

- the Planner classifies a task as database-related
- or another agent finds evidence pointing to the persistence layer

Typical flow:

1. Planner identifies database-related work
2. Frontend/API checks expose a persistence symptom
3. `Database Agent` reasons about schema, queries, storage assumptions, or migration issues
4. Its output feeds:
   - Reliability Agent
   - Triage Agent
   - Guardian

## Core Responsibilities

The Database Agent is responsible for:

- identifying DB-related root-cause candidates
- analyzing data correctness assumptions
- evaluating migration or schema-change risk
- reasoning about cache-vs-source-of-truth mismatches
- contributing evidence when application symptoms originate in persistence

## Inputs

The Database Agent should consume:

- imported stories/test cases with database or persistence language
- project logs
- API failure evidence
- repository context for schema or model code
- test-environment output
- observed symptoms such as stale data, mismatches, missing records, or broken writes

In the current product these inputs come from:

- story import
- repo/test-environment pull
- logs and metrics
- validation failures
- incident state

## Outputs

The Database Agent should produce:

- suspected database-related root cause
- migration/schema risk notes
- persistence-related diagnostic evidence
- recommended next checks
- handoff context for Reliability and Triage

## What It Does Today

Today this agent exists more as a reasoning and routing role than a full execution engine.

It currently contributes through:

- database-domain story classification
- backend orchestration state
- multi-agent coordination traces
- incident explanation context

It does not yet perform deep autonomous schema introspection or migration execution.

## Current Product Mapping

This agent maps most directly to the agent role:

- `database_analyst`

And conceptually to:

- database-related story routing
- triage reasoning
- persistence-oriented issue diagnosis

## Success Criteria

The Database Agent should eventually be judged on:

1. `db_root_cause_quality`
How often it correctly identifies persistence-related causes

2. `migration_risk_detection`
How often it correctly identifies unsafe schema or migration behavior

3. `data_integrity_reasoning_quality`
How well it explains stale, missing, duplicated, or inconsistent data symptoms

4. `handoff_quality`
How useful its output is for Reliability and Triage

5. `false_db_blame_rate`
How often it incorrectly attributes a problem to the database layer

## Known Failure Modes

Current likely failure modes:

- blaming the database when the actual issue is API logic
- reasoning about stale data without enough evidence
- weak schema/migration visibility
- over-relying on logs without true database introspection
- confusing caching issues with persistence issues

## Dashboard Representation

On the frontend, the Database Agent should appear as:

- the persistence specialist
- the agent that explains data-layer failures
- the source of schema/migration risk evidence

Recommended dashboard signals for this agent:

- suspected persistence issue
- data integrity alerts
- migration risk notes
- related API/story failures
- handoff state to Reliability

## Capabilities It Should Have When Mature

The mature Database Agent should be able to:

- inspect schema definitions and migrations
- reason about query patterns
- detect stale cache/data mismatch issues
- validate persistence correctness against story intent
- identify DB-related operational risk before deploy
- distinguish storage-layer faults from service-layer faults

## What It Should Not Do

The Database Agent should not:

- classify all stories initially
- own browser or API execution
- close incidents
- own release approval
- act as final auditor

Those belong to:

- Planner
- Frontend/API Test Agents
- Reliability Agent
- Guardian
- Oversight

## RL / Training Possibility

The Database Agent is a future candidate for specialized reasoning improvement, but not the first RL target.

A future Database Agent training setup could use:

- state:
  - story text
  - schema/migration context
  - logs and query evidence
  - data symptoms
- actions:
  - classify issue type
  - request schema evidence
  - request migration evidence
  - propose root cause
- reward:
  - correct diagnosis
  - fewer false database attributions
  - stronger downstream incident handling

This is more of a structured diagnostic-policy problem than the current incident-action RL loop.

## Refinement Roadmap

### Phase 1

- improve database-domain classification
- improve persistence-related reasoning
- improve dashboard visibility for DB-specific evidence

### Phase 2

- add migration and schema awareness from repos
- add stronger data-integrity checks
- improve distinction between cache and database problems

### Phase 3

- collect database-diagnostic trajectories
- train or evaluate database root-cause policies
- benchmark against real persistence failure cases

## Bottom Line

The Database Agent is the persistence specialist in OpenIncident X.

It should answer:

- is the problem really in the data layer?
- is schema/migration behavior causing the issue?
- is stored data correct and current?

It becomes most valuable when application failures are symptoms of deeper persistence problems.
