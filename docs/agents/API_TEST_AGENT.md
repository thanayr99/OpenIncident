# API Test Agent

## Purpose

The API Test Agent is responsible for validating backend endpoint behavior.

Its job is to:

- execute API checks
- validate status codes
- validate endpoint availability
- compare actual behavior against story/test-case expectations
- produce strong backend evidence when something fails

This agent turns API-related project requirements into executable service validation.

## Where It Sits In The Flow

The API Test Agent acts after:

- the Planner classifies a task as API-related
- the Environment/Repository Agent provides endpoint context or route hints

Typical flow:

1. Planner routes a story/test case to API validation
2. API path, method, and expected status are identified
3. `API Test Agent` executes the check
4. Failures become evidence for:
   - Reliability Agent
   - Triage Agent
   - Guardian

## Core Responsibilities

The API Test Agent is responsible for:

- running endpoint checks
- validating HTTP method and expected status
- measuring response time
- capturing response excerpts
- associating failures with stories or scenarios

## Inputs

The API Test Agent should consume:

- project base URL or deployed URL
- API path
- HTTP method
- expected status code
- labels and scenario context
- optional auth/context metadata in future versions

In the current product these inputs come from:

- project config
- imported stories/test cases
- API-check forms
- environment/repo discovery logic

## Outputs

The API Test Agent should produce:

- API validation result
- observed URL
- method
- expected status
- actual status
- response time
- response excerpt
- pass/fail signal

## What It Does Today

Today this agent already supports practical API execution.

It currently handles:

- API smoke checks
- endpoint status validation
- scenario labeling
- response capture for command center display

When an API check fails, the resulting evidence can contribute directly to incident creation and triage.

## Current Product Mapping

This agent maps most directly to:

- API validation endpoints in the backend
- story execution paths that infer API tests
- command-center API signal cards

It is surfaced through:

- latest API check result
- story execution results
- incident evidence
- project summary metrics

## Success Criteria

The API Test Agent should eventually be judged on:

1. `api_story_pass_rate`
How accurately it validates API-related stories

2. `endpoint_coverage_quality`
How often it targets the correct endpoint

3. `status_expectation_accuracy`
How often its expectation mapping is correct

4. `false_positive_rate`
How often it reports a failure that is not actually meaningful

5. `incident_signal_quality`
How useful its outputs are during incident diagnosis

## Known Failure Modes

Current likely failure modes:

- wrong API path inference
- wrong HTTP method assumption
- oversimplified status-only checks
- missing auth/context for protected endpoints
- treating a response code as sufficient proof of correctness
- weak differentiation between temporary deploy issues and real API regressions

## Dashboard Representation

On the frontend, the API Test Agent should appear as:

- the owner of backend endpoint validation
- the source of API health evidence
- the executor of API-related user stories

Recommended dashboard signals for this agent:

- API path
- method
- expected status
- actual status
- response time
- last response excerpt
- story/check association

## Capabilities It Should Have When Mature

The mature API Test Agent should be able to:

- infer likely API paths from repo structure
- validate payload shape, not only status code
- test authenticated and unauthenticated scenarios
- validate contract drift
- correlate API failure with logs and deploy context
- support chained endpoint workflows

## What It Should Not Do

The API Test Agent should not:

- classify stories initially
- own browser/UI validation
- own incident mitigation
- decide release approval alone
- perform final auditing

Those belong to:

- Planner
- Frontend Test Agent
- Reliability Agent
- Guardian
- Oversight

## RL / Training Possibility

The API Test Agent can become trainable later, but not through the current incident-action environment alone.

A future API Test Agent training setup could use:

- state:
  - endpoint candidates
  - repo/API context
  - prior response data
  - story intent
- actions:
  - choose endpoint
  - choose method
  - choose assertion type
  - choose follow-up check
- reward:
  - correct endpoint validation
  - lower false positives
  - stronger evidence for downstream triage

So this is a future specialized validation-policy problem, not the current Reliability-Agent RL problem.

## Refinement Roadmap

### Phase 1

- improve API path inference
- improve method/status inference from stories
- improve result visibility in the dashboard

### Phase 2

- add payload and schema validation
- add authenticated test support
- add contract-aware assertions

### Phase 3

- collect endpoint-selection trajectories
- train assertion/endpoint selection policies
- benchmark on diverse repo structures

## Bottom Line

The API Test Agent is the backend validation executor in OpenIncident X.

It should answer:

- does the endpoint respond?
- does it behave as expected?
- does the API-related story actually pass?

It is a core validation agent that feeds strong backend evidence into incidents, triage, and release gating.
