# OpenIncident X — Milestone 1

## Goal

Deliver one auditable incident lifecycle without replacing the existing OpenEnv/RL training environment.

## Existing capabilities to preserve

- FastAPI backend and React/Vite command center.
- Project registration, endpoint health checks, API/browser checks, log and metric ingestion.
- Incident/run/session state and triage summaries.
- Agent roster, coordination traces, guardian decisions, and user-story validation.
- Test-environment job records and the OpenEnv-style simulator, graders, and RL training artifacts.

## Milestone 1 acceptance criteria

1. A health or simulated failure can create a persistent incident/run.
2. Every investigation result is linked to the incident and includes evidence, timestamp, agent role, and status.
3. Log analysis and repository investigation can run as separate bounded tasks; triage records ranked hypotheses rather than asserting an unverified root cause.
4. Test runs are isolated from production, bounded by time/resource limits, and return structured results.
5. Human approval is required before any repository write, merge, deployment, rollback, or other production-changing action.
6. Project/tenant authorization applies to incident details, agent traces, logs, test runs, and approvals.
7. Tests cover account authentication, project isolation, incident lifecycle transitions, failure handling, and concurrent sessions.

## Required safety gates before enabling repository execution

The current test-environment runner launches repository commands using a local subprocess. Its command-string validator is a useful guardrail but is not a security boundary. Do not run untrusted repository code in the API process or on a host with production credentials.

Before enabling this capability for connected repositories, move install/test commands into a disposable isolated runner (container or VM) with:
- non-root execution and a read-only base image;
- a per-run workspace with no host or production mounts;
- no inherited secrets or production credentials;
- default-deny network access, with narrowly allowlisted package access if required;
- CPU, memory, process-count, disk, and wall-clock limits;
- cancellation and cleanup on timeout/failure;
- captured, size-limited stdout/stderr and an immutable run record.

Until that runner exists and is verified, use mocked test execution or trusted local development repositories only.

## Implementation sequence

### 1. Authentication and safe execution foundations
- Use salted, slow password hashing and migrate legacy hashes after successful login.
- Add regression tests for password verification and migration.
- Make the test-runner security boundary explicit; do not treat string blacklists as sandboxing.
- Add lifecycle/security regression tests before extending autonomy.

### 2. Incident lifecycle and event timeline
- Reuse existing run/session and project-event models where suitable.
- Define explicit states and allowed transitions.
- Persist agent task start/completion/failure, evidence references, triage hypotheses, test results, approval decisions, and resolution verification.
- Make retries idempotent and support cancellation without corrupting the incident state.

### 3. Bounded multi-agent investigation
- Monitor: detects a signal and opens/deduplicates an incident.
- Log Analyst: returns grouped errors and time windows with evidence references.
- Code Investigator: maps evidence to repository files/commits without changing code.
- Triage: ranks hypotheses with confidence and missing evidence.
- Test Guardian: checks test evidence and policy; it cannot grant human approval to itself.

### 4. Verified fix workflow
- Create a patch only in a separate branch/worktree.
- Run regression tests in the isolated runner.
- Require explicit human approval before merge/deploy.
- Verify service health after authorized deployment and retain a complete audit trail.

### 5. Evaluation
- Keep the simulator and RL lab as a separate first-class module.
- Compare agents against deterministic and random baselines on matched, held-out scenarios.
- Report success rate, time/steps to recovery, unsafe actions, premature closure, and confidence intervals.

## Non-goals for this milestone

- No autonomous production deployment.
- No unrestricted shell or browser access for LLM agents.
- No replacing the existing simulator or frontend wholesale.
- No claim of reliable diagnosis until evaluated against held-out incidents.
