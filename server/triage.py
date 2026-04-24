from __future__ import annotations

from models import RunTriageSummary, TriageRecommendation
from server.environment import ProductionIncidentEnv
from server.session_store import InMemorySessionStore


def _recommend(
    action_type: str,
    rationale: str,
    action_history: list[str],
    recommendations: list[TriageRecommendation],
) -> None:
    if action_type in action_history:
        return
    if any(item.action_type == action_type for item in recommendations):
        return
    recommendations.append(TriageRecommendation(action_type=action_type, rationale=rationale))


def build_run_triage(store: InMemorySessionStore, session_id: str) -> RunTriageSummary:
    session = store.get_session(session_id)
    run = store.get_run(session_id)
    environment = store.get_environment(session_id)
    state = environment.state()

    logs_text = " ".join(state.logs).lower()
    traces_text = " ".join(state.traces).lower()
    notes_text = " ".join(state.investigation_notes).lower()
    combined = " ".join([logs_text, traces_text, notes_text, state.incident_summary.lower(), state.user_impact.lower()])
    monitor_triggered = run.source == "monitor"
    has_browser_signal = "browser status=" in logs_text or "browser error=" in logs_text
    has_api_signal = "api status=" in logs_text or "api error=" in logs_text
    has_health_signal = "health status=" in logs_text or "health error=" in logs_text
    has_test_environment_signal = "test_environment status=" in logs_text or "test_env test_command=" in logs_text
    project_log_summary = None
    test_environment_run = None
    if run.project:
        try:
            project_log_summary = store.get_project_log_summary(run.project.project_id)
        except KeyError:
            project_log_summary = None
        test_environment_run = store.get_test_environment_run_for_incident(
            run.project.project_id,
            run_id=run.run_id,
            session_id=session.session_id,
        )

    suspected_root_cause = "Service degradation detected, but root cause still needs investigation."
    summary = f"{session.task_id.capitalize()} incident run for {state.service_name} is currently {state.current_status}."
    confidence = 0.46
    evidence: list[str] = []
    recommendations: list[TriageRecommendation] = []

    if run.source == "testing_environment" or has_test_environment_signal:
        suspected_root_cause = "The repository-level testing environment failed, which points to broken setup, failing test cases, dependency issues, or regressions introduced in code before deployment."
        summary = "A dedicated testing-environment run failed before release, so triage should start with the failing test command, setup steps, and the code paths those tests exercise."
        confidence = 0.83
        evidence.extend(
            [
                "The incident was opened directly from the repository testing environment.",
                "Attached incident logs include test-environment command details and captured output excerpts.",
            ]
        )
        if test_environment_run:
            evidence.append(f"Testing workspace: {test_environment_run.workspace_path}")
            if test_environment_run.install_result:
                evidence.append(
                    f"Install step exited with code {test_environment_run.install_result.return_code} using `{test_environment_run.install_result.command}`."
                )
            if test_environment_run.test_result:
                evidence.append(
                    f"Test step exited with code {test_environment_run.test_result.return_code} using `{test_environment_run.test_result.command}`."
                )
        _recommend("inspect_logs", "Review the test-environment stdout/stderr to identify the exact setup or assertion failure.", environment.action_history, recommendations)
        _recommend("inspect_code", "Inspect the code paths exercised by the failing repository tests.", environment.action_history, recommendations)
        _recommend("inspect_deploys", "Check recent code changes or dependency updates that could have broken predeploy tests.", environment.action_history, recommendations)
    elif monitor_triggered and has_browser_signal:
        suspected_root_cause = "A user-facing browser check failed, so the most likely issue is a broken render path, missing frontend content, or a backend dependency feeding that page."
        summary = "A browser-style validation triggered this run, so triage should focus first on the failing page flow and the APIs or templates behind it."
        confidence = 0.79
        evidence.extend(
            [
                "The run was auto-created from a browser validation failure.",
                "Attached logs show the browser check failed or the expected page content was missing.",
            ]
        )
        _recommend("inspect_logs", "Check render and API logs for the failing page flow.", environment.action_history, recommendations)
        _recommend("inspect_code", "Inspect the route, template, or frontend code behind the broken page.", environment.action_history, recommendations)
    elif monitor_triggered and has_api_signal:
        suspected_root_cause = "An API validation failed, which points to a broken backend endpoint, dependency issue, or contract mismatch."
        summary = "An API check triggered this run, so the first investigation path should be the failing endpoint and the services it depends on."
        confidence = 0.78
        evidence.extend(
            [
                "The run was auto-created from an API validation failure.",
                "Attached logs show an unexpected API status or transport-level failure.",
            ]
        )
        _recommend("inspect_logs", "Review server logs and recent changes around the failing endpoint.", environment.action_history, recommendations)
        _recommend("inspect_code", "Inspect the backend handler and dependency chain for this API.", environment.action_history, recommendations)
    elif monitor_triggered and has_health_signal:
        suspected_root_cause = "A health check failure triggered this run, so the service may be down, partially unavailable, or failing a core dependency at startup/runtime."
        summary = "A health monitor failure opened this run, so triage should start with service availability, runtime errors, and the latest deploy or config changes."
        confidence = 0.74
        evidence.extend(
            [
                "The run was auto-created from a website health check failure.",
                "Attached logs show the health endpoint returned an unhealthy or unreachable result.",
            ]
        )
        _recommend("inspect_logs", "Check runtime logs around startup failures or dependency outages.", environment.action_history, recommendations)
        _recommend("inspect_deploys", "Review the latest deploy or config change that may have broken service health.", environment.action_history, recommendations)
    elif "strip" in combined and "nonetype" in combined:
        suspected_root_cause = "A null-handling bug is reaching string normalization logic and causing the profile request path to fail."
        summary = "The service is failing on a null value that reaches a string operation without a guard."
        confidence = 0.88
        evidence.extend(
            [
                "Logs mention a NoneType failure alongside a string operation.",
                "Trace evidence points to the normalization path during the failing request.",
            ]
        )
        _recommend("inspect_code", "Review the normalization function and add a null guard.", environment.action_history, recommendations)
        _recommend("apply_fix", "Patch the failing code path so null input no longer crashes the request.", environment.action_history, recommendations)
    elif "ttl" in combined or "cache" in combined or "invalidation" in combined:
        suspected_root_cause = "Cached data is likely stale because TTL settings and invalidation behavior are out of sync."
        summary = "The incident looks like a correctness issue driven by stale cached values rather than a total outage."
        confidence = 0.82
        evidence.extend(
            [
                "Signals mention cache hits or stale values near the failing path.",
                "Configuration or trace evidence suggests invalidation is not keeping up with updates.",
            ]
        )
        _recommend("inspect_config", "Confirm TTL settings and cache invalidation controls.", environment.action_history, recommendations)
        _recommend("apply_fix", "Reduce TTL and repair invalidation logic so fresh values reach the request path.", environment.action_history, recommendations)
    elif "feature flag" in combined or "queue_depth" in combined or "request amplification" in combined or "n+1" in combined:
        suspected_root_cause = "A rollout or feature flag appears to have introduced request amplification, and concurrency is now too low for the new load pattern."
        summary = "This looks like a rollout-driven performance incident with amplified downstream work and queuing."
        confidence = 0.84
        evidence.extend(
            [
                "Signals suggest request amplification or repeated downstream work.",
                "Operational metrics point to queueing pressure and resource saturation.",
            ]
        )
        _recommend("inspect_deploys", "Check the latest rollout or feature flag change that may have increased request fanout.", environment.action_history, recommendations)
        _recommend("apply_fix", "Disable the problematic feature or increase concurrency to stabilize traffic handling.", environment.action_history, recommendations)
        _recommend("add_monitor", "Add alerting around latency and rollout-related regressions.", environment.action_history, recommendations)
    elif "api error=" in combined or "expected 200, got" in combined:
        suspected_root_cause = "A backend API contract or server-side path is returning an unexpected status and needs investigation."
        summary = "An API validation failure triggered this run, so the most likely issue is in the server-side endpoint or its dependencies."
        confidence = 0.72
        evidence.extend(
            [
                "The run was created from an API validation failure.",
                "The attached evidence shows an unexpected HTTP status from the target endpoint.",
            ]
        )
        _recommend("inspect_logs", "Gather server logs around the failing endpoint to locate the exception or dependency failure.", environment.action_history, recommendations)
        _recommend("inspect_code", "Inspect the endpoint implementation and the code it depends on.", environment.action_history, recommendations)
    elif "browser error=" in combined or "expected page text not found" in combined:
        suspected_root_cause = "The website is reachable, but the user-facing page is missing expected content, suggesting a frontend regression or incomplete render path."
        summary = "A browser-style validation failed, which usually means the UI path is broken even though the service still responds."
        confidence = 0.7
        evidence.extend(
            [
                "The run was created from a browser validation failure.",
                "The attached evidence indicates missing page content rather than a transport-level outage.",
            ]
        )
        _recommend("inspect_code", "Inspect the frontend route or template responsible for the missing content.", environment.action_history, recommendations)
        _recommend("inspect_logs", "Check server-side render or API logs that feed this page.", environment.action_history, recommendations)
    else:
        evidence.extend(
            [
                "The run contains a failure signal, but the current evidence is still broad.",
                "More investigation is needed to narrow the incident to a code path or configuration issue.",
            ]
        )
        _recommend("inspect_logs", "Start with logs to narrow the failing path.", environment.action_history, recommendations)
        _recommend("inspect_metrics", "Review metrics to distinguish correctness, latency, and availability problems.", environment.action_history, recommendations)

    if project_log_summary and project_log_summary.total_entries:
        evidence.append(
            f"Project logs contain {project_log_summary.error_entries} error entries and {project_log_summary.warning_entries} warnings."
        )
        if project_log_summary.latest_errors:
            evidence.append(f"Latest log signal: {project_log_summary.latest_errors[0]}")

    if test_environment_run and test_environment_run.test_result:
        excerpt = (test_environment_run.test_result.stderr or test_environment_run.test_result.stdout or "").strip()
        if excerpt:
            evidence.append(f"Test environment output excerpt: {excerpt[:180]}")

    if state.service_restored:
        summary = f"{summary} The service currently appears restored, so triage should focus on validation and prevention."
        _recommend("add_monitor", "Add recurrence prevention or alerting after recovery.", environment.action_history, recommendations)
    elif not state.root_cause_confirmed:
        _recommend("identify_root_cause", "Record the diagnosis once the evidence is strong enough.", environment.action_history, recommendations)

    return RunTriageSummary(
        run_id=run.run_id,
        session_id=session.session_id,
        status=run.status,
        summary=summary,
        suspected_root_cause=suspected_root_cause,
        confidence=round(confidence, 2),
        evidence=evidence,
        recommended_actions=recommendations,
    )
