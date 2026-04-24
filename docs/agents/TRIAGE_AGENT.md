# Triage Agent

## Purpose

The Triage Agent is responsible for turning raw failure evidence into a structured diagnosis.

Its job is to:

- summarize what failed
- infer the most likely root cause
- estimate confidence
- organize evidence
- recommend next actions

This agent makes incidents understandable and actionable for both humans and downstream agents.

## Where It Sits In The Flow

The Triage Agent acts after:

- checks or stories fail
- an incident is opened or updated
- evidence from logs, metrics, browser/API checks, or the Reliability Agent is available

Typical flow:

1. Validation fails
2. Incident opens
3. Observability and Reliability provide evidence
4. `Triage Agent` produces a diagnosis
5. Guardian and Oversight consume the result

## Core Responsibilities

The Triage Agent is responsible for:

- summarizing incident context
- proposing suspected root cause
- measuring confidence
- listing the strongest evidence
- recommending the most relevant next actions

## Inputs

The Triage Agent should consume:

- incident state
- browser/API/health check failures
- logs and metrics summaries
- Reliability Agent findings
- project context
- story/test-case failure context

In the current product these inputs come from:

- incident runs
- project evidence
- log summaries
- validation snapshots
- runtime incident state

## Outputs

The Triage Agent should produce:

- summary
- suspected root cause
- confidence score
- evidence list
- recommended actions
- generated-at timestamp

## What It Does Today

Today the Triage Agent is already visible in the product as AI-style diagnosis output.

It currently supports:

- structured triage output for incident runs
- summary generation
- suspected root cause generation
- evidence listing
- action recommendations

This makes it one of the clearest “reasoning agent” surfaces in the app today.

## Current Product Mapping

This agent maps most directly to:

- triage output shown in the command center
- incident run diagnosis
- reliability and evidence summaries

It is surfaced through:

- run triage cards
- command-center triage panels
- incident diagnosis JSON/output

## Success Criteria

The Triage Agent should eventually be judged on:

1. `triage_accuracy`
How often the suspected root cause is directionally correct

2. `evidence_quality`
How relevant and useful the listed evidence is

3. `confidence_calibration`
How well the confidence score matches actual correctness

4. `recommendation_quality`
How helpful the recommended actions are

5. `operator_usefulness`
How much the output helps users understand what to do next

## Known Failure Modes

Current likely failure modes:

- overly generic summaries
- weak root-cause specificity
- confidence that is too high for weak evidence
- repeated recommendations with low operational value
- diagnosis that mirrors symptoms rather than cause

## Dashboard Representation

On the frontend, the Triage Agent should appear as:

- the diagnosis layer
- the interpreter of incident evidence
- the source of likely root cause and next-step guidance

Recommended dashboard signals for this agent:

- triage summary
- suspected root cause
- confidence score
- evidence list
- recommended actions

## Capabilities It Should Have When Mature

The mature Triage Agent should be able to:

- generate more precise root-cause hypotheses
- calibrate confidence against evidence quality
- separate symptom from cause
- recommend next steps that reduce ambiguity quickly
- compare multiple possible hypotheses

## What It Should Not Do

The Triage Agent should not:

- classify stories initially
- execute browser/API checks directly
- choose final remediation actions alone
- act as the release gate
- perform final audit of all agents

Those belong to:

- Planner
- Frontend/API Test Agents
- Reliability Agent
- Guardian
- Oversight

## RL / Training Possibility

The Triage Agent is a good future candidate for structured reasoning improvement, but it is not the first direct RL target.

A future Triage training setup could use:

- state:
  - incident evidence
  - check failures
  - log summaries
  - reliability notes
- actions:
  - choose hypothesis
  - choose confidence
  - choose evidence set
  - choose recommendation
- reward:
  - correct diagnosis
  - calibrated confidence
  - better downstream resolution

This is more of a diagnosis-ranking and reasoning-calibration problem than the current Reliability-Agent action problem.

## Refinement Roadmap

### Phase 1

- improve summary specificity
- improve evidence selection
- improve confidence calibration

### Phase 2

- add richer multi-hypothesis triage
- improve recommendation quality
- tie triage more tightly to operational outcomes

### Phase 3

- collect triage-quality datasets
- benchmark diagnosis accuracy
- train more specialized diagnosis policies

## Bottom Line

The Triage Agent is the diagnosis explainer in OpenIncident X.

It should answer:

- what most likely went wrong?
- how confident are we?
- what evidence supports that?
- what should happen next?

It makes the incident system understandable instead of just reactive.
