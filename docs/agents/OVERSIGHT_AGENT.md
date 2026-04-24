# Oversight Agent

## Purpose

The Oversight Agent is the auditing and trust layer in OpenIncident X.

Its job is to:

- review the conclusions of other agents
- identify weak reasoning or premature certainty
- reduce false positives and unsafe approvals
- verify that closure quality is actually acceptable

This agent exists to increase trust in the whole system, not to replace the domain agents.

## Where It Sits In The Flow

The Oversight Agent acts near the end of the workflow, once other agents have already produced outputs.

Typical flow:

1. Planner routes work
2. Validation agents execute
3. Reliability and Triage produce incident reasoning
4. Guardian decides readiness
5. `Oversight Agent` audits the conclusions

## Core Responsibilities

The Oversight Agent is responsible for:

- checking whether other agents' outputs are well-supported
- identifying weak or overconfident conclusions
- detecting false positives or premature closure
- increasing trust in final decisions

## Inputs

The Oversight Agent should consume:

- Planner output
- validation results
- incident state
- triage output
- Guardian decision
- supporting evidence
- action history

In the current product these inputs come from:

- project summaries
- agent coordination traces
- incident runs
- triage state
- readiness state

## Outputs

The Oversight Agent should produce:

- audit notes
- confidence adjustments or caution flags
- approval concerns
- escalation recommendations
- final trust commentary

## What It Does Today

Today the Oversight Agent exists mostly as a conceptual and workflow role.

It currently contributes through:

- agent role modeling
- coordination traces
- dashboard representation
- architecture-level intent for auditing

It is not yet deeply autonomous, and that is okay at this stage.

## Current Product Mapping

This agent maps most directly to the role:

- `oversight`

And conceptually to:

- final audit
- trust verification
- false-positive reduction

## Success Criteria

The Oversight Agent should eventually be judged on:

1. `false_positive_reduction`
How often it catches weak or incorrect conclusions

2. `unsafe_approval_prevention`
How often it prevents premature confidence or closure

3. `audit_quality`
How useful and justified its audit notes are

4. `trust_improvement`
How much confidence users can place in the system with Oversight active

5. `non_intrusive_value`
How often it improves quality without becoming noisy or obstructive

## Known Failure Modes

Current likely failure modes:

- becoming too generic to be useful
- blocking too often without strong justification
- repeating what Triage or Guardian already said
- missing subtle weak-reasoning cases
- adding friction without adding trust

## Dashboard Representation

On the frontend, the Oversight Agent should appear as:

- the final auditor
- the trust and review layer
- the source of cautionary or confirmatory audit notes

Recommended dashboard signals for this agent:

- audit status
- trust level
- weak-evidence warnings
- closure-quality notes
- escalation recommendation

## Capabilities It Should Have When Mature

The mature Oversight Agent should be able to:

- detect overconfident triage
- detect weak release approvals
- verify whether incident closure is actually justified
- highlight missing evidence
- reduce trust mistakes without slowing everything down too much

## What It Should Not Do

The Oversight Agent should not:

- run first-pass validation
- classify stories
- choose the first remediation path
- execute browser/API checks directly
- own deployment environment preparation

Those belong to:

- Planner
- Frontend/API Test Agents
- Reliability Agent
- Environment Agent

## RL / Training Possibility

The Oversight Agent is a future candidate for audit-policy or critique-policy learning.

A future Oversight training setup could use:

- state:
  - outputs from other agents
  - confidence levels
  - evidence quality
  - incident outcomes
- actions:
  - approve
  - caution
  - request more evidence
  - escalate
- reward:
  - fewer false positives
  - fewer unsafe approvals
  - better final trustworthiness

This is a governance and critique-learning problem, not the current Reliability-Agent action loop.

## Refinement Roadmap

### Phase 1

- improve audit-note quality
- improve linkage to triage and guardian outputs
- surface trust-related warnings clearly

### Phase 2

- add structured audit criteria
- detect weak-evidence patterns
- reduce duplicate warning noise

### Phase 3

- collect oversight-decision datasets
- benchmark trust improvements
- train critique or audit policies

## Bottom Line

The Oversight Agent is the trust and audit layer in OpenIncident X.

It should answer:

- do we really trust this conclusion?
- is the evidence strong enough?
- are we closing or approving too early?

It makes the system safer and more credible.
