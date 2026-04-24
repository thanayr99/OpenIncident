# Observability Agent

## Purpose

The Observability Agent is responsible for runtime evidence collection and correlation.

Its job is to:

- ingest logs
- summarize operational signals
- correlate failures with evidence
- surface the most relevant runtime clues
- support triage and incident response with real evidence

This agent is the bridge between raw production signals and useful operational reasoning.

## Where It Sits In The Flow

The Observability Agent acts when:

- logs are manually ingested
- a log connector is configured
- checks fail and runtime evidence is needed
- incidents need supporting evidence

Typical flow:

1. Validation or user stories fail
2. Logs or metrics are pulled
3. `Observability Agent` summarizes runtime evidence
4. That evidence feeds:
   - Reliability Agent
   - Triage Agent
   - Guardian

## Core Responsibilities

The Observability Agent is responsible for:

- collecting logs and runtime signals
- summarizing errors, warnings, and patterns
- associating evidence with project failures
- helping distinguish real incidents from weak signals
- improving diagnosis quality with operational context

## Inputs

The Observability Agent should consume:

- raw logs
- JSON logs
- connected log endpoint output
- project metrics
- story failure results
- browser/API check failures
- incident context

In the current product these inputs come from:

- manual log ingestion
- HTTP log connector
- project metric ingestion
- failed validations
- incident state

## Outputs

The Observability Agent should produce:

- log summaries
- evidence snippets
- likely correlated failures
- signal severity notes
- useful context for triage and reliability work

## What It Does Today

Today this agent is fairly practical already.

It currently supports:

- manual log ingestion
- connected log pulling
- log summaries
- metric summaries
- project event history
- evidence flow into incident state and story status

It is still more logs-first than fully metrics/traces-driven.

## Current Product Mapping

This agent maps most directly to:

- log ingestion APIs
- log connector APIs
- metric ingestion APIs
- project events
- log and metric summary endpoints

It is surfaced through:

- command-center evidence cards
- log summary UI
- incident evidence
- project summaries

## Success Criteria

The Observability Agent should eventually be judged on:

1. `evidence_relevance`
How often it surfaces the useful runtime evidence

2. `signal_correlation_quality`
How well it connects logs and metrics to actual failures

3. `noise_reduction_quality`
How effectively it reduces irrelevant runtime noise

4. `incident_support_quality`
How useful its output is during incident handling

5. `connector_reliability`
How consistently it pulls and summarizes runtime evidence

## Known Failure Modes

Current likely failure modes:

- too much raw noise and not enough summarization
- weak correlation between evidence and failures
- missing trace-level context
- over-reliance on pasted logs instead of live integrations
- incomplete metric interpretation

## Dashboard Representation

On the frontend, the Observability Agent should appear as:

- the runtime evidence collector
- the source of log and metrics context
- the link between failures and operational signals

Recommended dashboard signals for this agent:

- log connector status
- recent log pull result
- summary of error levels
- relevant metric spikes
- incident evidence excerpts

## Capabilities It Should Have When Mature

The mature Observability Agent should be able to:

- pull logs automatically from connected systems
- summarize incidents from logs, metrics, and traces together
- detect recurring signal patterns
- correlate deploys with spikes or regressions
- distinguish symptom noise from root-cause evidence
- provide concise evidence packets to other agents

## What It Should Not Do

The Observability Agent should not:

- classify stories at the start
- own browser or API execution
- choose remediation actions itself
- close incidents
- act as the final release gate

Those belong to:

- Planner
- Frontend/API Test Agents
- Reliability Agent
- Guardian

## RL / Training Possibility

The Observability Agent is a future candidate for evidence-ranking or signal-selection learning.

A future training setup could use:

- state:
  - logs
  - metrics
  - traces
  - failure context
- actions:
  - choose evidence to surface
  - choose correlation hypothesis
  - rank signal relevance
- reward:
  - better downstream diagnosis
  - reduced noise
  - higher incident-resolution efficiency

This is more of a ranking and evidence-selection problem than the current Reliability-Agent RL loop.

## Refinement Roadmap

### Phase 1

- improve log summarization quality
- improve project-level evidence visibility
- tighten linkage between logs and failures

### Phase 2

- strengthen metrics and trace correlation
- add richer connector support
- improve severity and anomaly summaries

### Phase 3

- train evidence-ranking policies
- benchmark evidence usefulness across incident types
- integrate more deeply with automated triage

## Bottom Line

The Observability Agent is the runtime evidence specialist in OpenIncident X.

It should answer:

- what operational evidence is actually relevant?
- what do the logs and metrics suggest?
- how does this signal connect to the failing project behavior?

It makes the rest of the incident system much smarter by turning raw signals into usable evidence.
