# Frontend Test Agent

## Purpose

The Frontend Test Agent is responsible for validating user-facing behavior.

Its job is to:

- run browser-based checks
- verify visible UI content
- validate page flows
- test user interactions
- determine whether frontend stories actually work

This agent is how OpenIncident X turns frontend user intent into executable browser validation.

## Where It Sits In The Flow

The Frontend Test Agent acts after:

- the Planner has classified work as frontend-related
- the Environment/Repository Agent has prepared enough project context

Typical flow:

1. Planner marks a story or test case as frontend
2. Frontend routes/selectors/text are inferred or provided
3. `Frontend Test Agent` runs rendered browser checks
4. Failures become evidence for:
   - Reliability Agent
   - Triage Agent
   - Guardian

## Core Responsibilities

The Frontend Test Agent is responsible for:

- running Playwright/browser checks
- validating page load success
- checking expected text
- checking expected selectors
- validating navigation flows
- mapping frontend failures back to user stories

## Inputs

The Frontend Test Agent should consume:

- project base URL or deployed URL
- discovered frontend routes
- story/test-case path hints
- expected visible text
- expected selectors
- labels for each scenario
- optional repo-derived context

In the current product these inputs come from:

- project config
- frontend discovery
- imported bulk stories/test cases
- browser-check forms and automation

## Outputs

The Frontend Test Agent should produce:

- browser validation results
- observed URL
- status
- status code if available
- page title
- response time
- response excerpt
- actionable failure evidence

## What It Does Today

Today this agent is already one of the more concrete execution agents.

It currently supports:

- browser path checks
- rendered Playwright checks
- expected text validation
- selector validation
- result capture for command-center display

When failures occur, those results can open incidents automatically.

## Current Product Mapping

This agent maps most directly to:

- browser validation flows in the backend
- frontend-discovery logic
- story execution that uses browser-style validation

It is surfaced through:

- latest browser check result
- signal matrix / command-center overview
- story execution status
- incident evidence

## Success Criteria

The Frontend Test Agent should eventually be judged on:

1. `frontend_story_pass_rate`
How accurately it validates frontend stories

2. `route_discovery_quality`
How often it picks the right route or page

3. `selector_accuracy`
How often it checks the right element

4. `false_positive_rate`
How often it flags a failure when the UI is actually acceptable

5. `incident_evidence_quality`
How useful its outputs are for triage

## Known Failure Modes

Current likely failure modes:

- checking the wrong route
- expecting the wrong text
- fragile selectors
- false failures caused by rendering delay
- relying too heavily on a single text token
- validating only presence, not actual user flow quality

## Dashboard Representation

On the frontend, the Frontend Test Agent should appear as:

- the owner of browser validation
- the source of page-level health evidence
- the executor of frontend user stories

Recommended dashboard signals for this agent:

- latest browser check
- route being checked
- expected text/selector
- response time
- screenshot or excerpt in future versions
- story-to-check mapping

## Capabilities It Should Have When Mature

The mature Frontend Test Agent should be able to:

- discover likely routes automatically
- infer frontend assertions from stories
- run multi-step flows
- detect broken navigation
- detect missing UI states
- validate auth-protected flows
- attach richer visual evidence

## What It Should Not Do

The Frontend Test Agent should not:

- classify stories initially
- own API contract validation
- choose release safety
- decide root cause by itself
- close incidents

Those belong to:

- Planner
- API Test Agent
- Guardian
- Reliability/Triage

## RL / Training Possibility

This agent can eventually become trainable, but not through the same incident-action space as the Reliability Agent.

A future Frontend Test Agent training setup could use:

- state:
  - route info
  - DOM evidence
  - prior check outputs
  - story/test-case intent
- actions:
  - choose route
  - choose selector
  - choose assertion
  - continue navigation
- reward:
  - correct story validation
  - reduced false positives
  - stronger evidence quality

This is more like browser-task policy learning than incident-response RL.

## Refinement Roadmap

### Phase 1

- improve route detection
- improve assertion inference from stories
- improve browser-check ergonomics

### Phase 2

- add multi-step user-flow testing
- add smarter selector fallback
- add screenshot capture and visual evidence

### Phase 3

- collect execution trajectories
- train route/assertion selection models
- benchmark against labeled frontend test suites

## Bottom Line

The Frontend Test Agent is the user-interface executor in OpenIncident X.

It should answer:

- does the page load?
- is the expected UI present?
- does the frontend story actually work?

It is a core validation agent, and it feeds strong evidence into incidents, triage, and release gating.
