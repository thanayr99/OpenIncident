from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple

from models import IncidentAction, IncidentObservation, ActionType, IncidentTask
from tasks import TASK_REGISTRY


class ProductionIncidentEnv:
    def __init__(self, task_id: str = "easy", max_steps: int | None = None) -> None:
        if task_id not in TASK_REGISTRY:
            raise ValueError(f"Unsupported task_id: {task_id}")
        self.task = TASK_REGISTRY[task_id].model_copy(deep=True)
        self.max_steps = max_steps or self.task.max_steps
        self.action_history: List[str] = []
        self._revealed: Dict[str, bool] = {}
        self._checks: Dict[str, bool] = {}
        self._state = self._build_initial_state()

    def _build_initial_state(self) -> IncidentObservation:
        self.action_history = []
        self._revealed = {
            "logs": False,
            "metrics": False,
            "traces": False,
            "deploys": False,
            "config": False,
            "code": False,
        }
        self._checks = {check_name: False for check_name in self.task.expected_checks}
        state = IncidentObservation(
            incident_id=f"incident-{self.task.task_id}",
            difficulty=self.task.difficulty,
            service_name=self.task.service_name,
            incident_summary=self.task.incident_summary,
            current_status="investigating",
            severity=self.task.severity,
            user_impact=self.task.user_impact,
            logs=deepcopy(self.task.initial_logs),
            metrics=deepcopy(self.task.initial_metrics),
            traces=deepcopy(self.task.initial_traces),
            recent_deploys=[],
            config_snapshot={},
            code_snippet="",
            available_dashboards=deepcopy(self.task.available_dashboards),
            investigation_notes=[],
            suspected_root_cause=None,
            root_cause_confirmed=False,
            mitigation_applied=False,
            service_restored=False,
            monitoring_added=False,
            passed_checks=0,
            failed_checks=len(self.task.expected_checks),
            reliability_score=self.task.baseline_reliability,
            steps_taken=0,
            max_steps=self.max_steps,
            last_action=None,
            last_action_error=None,
        )
        return state

    def reset(self) -> IncidentObservation:
        self._state = self._build_initial_state()
        return self.state()

    def state(self) -> IncidentObservation:
        return self._state.model_copy(deep=True)

    def _normalize(self, value: str | None) -> str:
        return (value or "").strip().lower()

    def _matches_any(self, content: str | None, options: List[str]) -> bool:
        normalized = self._normalize(content)
        return any(option in normalized for option in options)

    def _add_note(self, note: str) -> None:
        if note not in self._state.investigation_notes:
            self._state.investigation_notes.append(note)

    def _set_last_action(self, action: IncidentAction) -> None:
        if action.content:
            self._state.last_action = f"{action.action_type.value}:{action.content}"
        elif action.target:
            self._state.last_action = f"{action.action_type.value}:{action.target}"
        else:
            self._state.last_action = action.action_type.value
        self._state.last_action_error = None
        self.action_history.append(action.action_type.value)

    def _bump_reliability(self, delta: float) -> None:
        self._state.reliability_score = round(max(0.0, min(100.0, self._state.reliability_score + delta)), 2)

    def _sync_checks(self) -> None:
        if "root_cause_identified" in self._checks:
            self._checks["root_cause_identified"] = self._state.root_cause_confirmed
        if "safe_monitoring_added" in self._checks:
            self._checks["safe_monitoring_added"] = self._state.monitoring_added

        self._state.passed_checks = sum(1 for passed in self._checks.values() if passed)
        self._state.failed_checks = len(self._checks) - self._state.passed_checks

    def _compose_reward(self, action_reward: float) -> float:
        reward = (
            action_reward
            + (self._state.passed_checks * 0.12)
            - (self._state.failed_checks * 0.10)
            + (0.15 if self._state.root_cause_confirmed else 0.0)
            + (0.20 if self._state.service_restored else 0.0)
            + (0.08 if self._state.monitoring_added else 0.0)
            + (self._state.reliability_score * 0.003)
        )
        return round(max(0.0, min(1.0, reward)), 4)

    def _reveal(self, kind: str) -> Tuple[float, Dict[str, Any]]:
        if self._revealed[kind]:
            self._state.last_action_error = f"{kind} already inspected"
            self._bump_reliability(-2)
            return -0.01, {"action_result": "redundant_inspection"}

        self._revealed[kind] = True
        if kind == "logs":
            self._state.logs.extend(self.task.hidden_logs)
            self._add_note("Expanded log context reviewed.")
            reward = 0.02
        elif kind == "metrics":
            self._state.metrics.update(self.task.hidden_metrics)
            self._add_note("Deep metrics checked for incident impact.")
            reward = 0.02
        elif kind == "traces":
            self._state.traces.extend(self.task.hidden_traces)
            self._add_note("Request traces inspected.")
            reward = 0.03
        elif kind == "deploys":
            self._state.recent_deploys = deepcopy(self.task.recent_deploys)
            self._add_note("Recent deploy history inspected.")
            reward = 0.02
        elif kind == "config":
            self._state.config_snapshot = deepcopy(self.task.config_snapshot)
            self._add_note("Runtime configuration inspected.")
            reward = 0.02
        else:
            self._state.code_snippet = self.task.code_snippet
            self._add_note("Relevant code path inspected.")
            reward = 0.03

        return reward, {"action_result": f"revealed_{kind}"}

    def _identify_root_cause(self, content: str | None) -> Tuple[float, Dict[str, Any]]:
        if self._matches_any(content, self.task.root_cause_keywords):
            self._state.suspected_root_cause = content
            self._state.root_cause_confirmed = True
            self._add_note("Root cause hypothesis confirmed.")
            self._bump_reliability(10)
            self._sync_checks()
            return 0.20, {"action_result": "root_cause_confirmed"}

        self._state.suspected_root_cause = content
        self._state.last_action_error = "Diagnosis did not match the incident evidence"
        self._bump_reliability(-4)
        self._sync_checks()
        return -0.10, {"action_result": "root_cause_incorrect"}

    def _mark_restored_checks(self) -> None:
        for check_name in self._checks:
            if check_name == "safe_monitoring_added":
                continue
            self._checks[check_name] = True
        self._sync_checks()

    def _apply_valid_fix(self, note: str) -> None:
        self._state.mitigation_applied = True
        self._state.service_restored = True
        self._state.current_status = "mitigated"
        self._add_note(note)
        self._mark_restored_checks()
        self._bump_reliability(25)
        self._update_recovered_metrics()

    def _apply_partial_fix(self, note: str) -> None:
        self._state.mitigation_applied = True
        self._state.current_status = "partially_mitigated"
        self._add_note(note)
        partial_targets = self.task.expected_checks[: max(1, len(self.task.expected_checks) - 2)]
        for check_name in partial_targets:
            self._checks[check_name] = True
        self._sync_checks()
        self._bump_reliability(8)
        self._update_partial_metrics()

    def _apply_harmful_action(self, error: str) -> None:
        self._state.last_action_error = error
        self._state.current_status = "degraded"
        self._bump_reliability(-10)
        self._sync_checks()

    def _update_recovered_metrics(self) -> None:
        if self.task.task_id == "easy":
            self._state.metrics.update({"error_rate": 0.4, "p95_latency_ms": 120.0, "request_success_rate": 99.5})
        elif self.task.task_id == "medium":
            self._state.metrics.update({"checkout_mismatch_rate": 0.2, "error_rate": 0.5, "p95_latency_ms": 140.0})
        else:
            self._state.metrics.update({"timeout_rate": 0.8, "p95_latency_ms": 420.0, "cpu_usage": 48.0, "worker_utilization": 62.0})
            if self._revealed["metrics"]:
                self._state.metrics.update({"queue_depth": 20.0, "request_fanout": 1.4})

    def _update_partial_metrics(self) -> None:
        if self.task.task_id == "easy":
            self._state.metrics.update({"error_rate": 4.5, "p95_latency_ms": 210.0, "request_success_rate": 95.0})
        elif self.task.task_id == "medium":
            self._state.metrics.update({"checkout_mismatch_rate": 2.8, "error_rate": 0.9, "p95_latency_ms": 165.0})
        else:
            self._state.metrics.update({"timeout_rate": 9.0, "p95_latency_ms": 2100.0, "cpu_usage": 72.0, "worker_utilization": 80.0})
            if self._revealed["metrics"]:
                self._state.metrics.update({"queue_depth": 180.0, "request_fanout": 6.0})

    def _apply_fix(self, content: str | None) -> Tuple[float, Dict[str, Any]]:
        normalized = self._normalize(content)
        if self._matches_any(normalized, self.task.valid_mitigations):
            self._apply_valid_fix("Full mitigation applied successfully.")
            return 0.30, {"action_result": "full_mitigation"}
        if self._matches_any(normalized, self.task.partial_mitigations):
            self._apply_partial_fix("Partial mitigation reduced impact but did not fully recover service.")
            return 0.12, {"action_result": "partial_mitigation"}
        if self._matches_any(normalized, self.task.harmful_actions):
            self._apply_harmful_action("Mitigation worsened the incident or ignored the evidence")
            return -0.25, {"action_result": "harmful_mitigation"}

        self._state.last_action_error = "Submitted mitigation did not match any known recovery path"
        self._bump_reliability(-6)
        return -0.12, {"action_result": "unknown_mitigation"}

    def _rollback_deploy(self) -> Tuple[float, Dict[str, Any]]:
        if self.task.task_id == "easy":
            self._apply_partial_fix("Rollback removed the bad normalization change, but follow-up patch is still recommended.")
            return 0.15, {"action_result": "rollback_helpful"}
        if self.task.task_id == "medium":
            self._apply_partial_fix("Rollback reduced stale pricing, but cache invalidation still needs correction.")
            return 0.10, {"action_result": "rollback_partial"}
        if self._state.root_cause_confirmed:
            self._apply_partial_fix("Rollback reduced request amplification, but capacity and monitoring still need attention.")
            return 0.15, {"action_result": "rollback_partial"}
        self._apply_harmful_action("Rollback was attempted before confirming the rollout issue")
        return -0.08, {"action_result": "rollback_premature"}

    def _restart_service(self) -> Tuple[float, Dict[str, Any]]:
        self._state.last_action_error = "Restarting the service does not address the underlying production issue"
        self._bump_reliability(-5)
        return -0.05, {"action_result": "restart_unhelpful"}

    def _scale_service(self) -> Tuple[float, Dict[str, Any]]:
        if self.task.task_id == "hard":
            self._apply_partial_fix("Scaling the service reduced queuing pressure but did not remove the root cause.")
            return 0.10, {"action_result": "scale_partial"}
        self._state.last_action_error = "Scaling does not help this incident pattern"
        self._bump_reliability(-5)
        return -0.05, {"action_result": "scale_unhelpful"}

    def _add_monitor(self) -> Tuple[float, Dict[str, Any]]:
        if self._state.root_cause_confirmed or self._state.service_restored:
            if self._state.monitoring_added:
                self._state.last_action_error = "Monitor already added"
                return -0.01, {"action_result": "duplicate_monitor"}
            self._state.monitoring_added = True
            self._checks["safe_monitoring_added"] = True
            self._add_note("Post-incident monitoring added for recurrence prevention.")
            self._bump_reliability(8)
            self._sync_checks()
            return 0.08, {"action_result": "monitor_added"}
        self._state.last_action_error = "Monitoring should follow diagnosis or mitigation"
        self._bump_reliability(-2)
        return -0.02, {"action_result": "monitor_premature"}

    def _resolve_incident(self) -> Tuple[float, bool, Dict[str, Any]]:
        if self._state.service_restored:
            self._state.current_status = "resolved"
            self._add_note("Incident resolved after service restoration.")
            self._sync_checks()
            return 0.10, True, {"action_result": "incident_resolved"}
        self._state.last_action_error = "Cannot resolve incident before service is restored"
        return -0.10, False, {"action_result": "resolve_too_early"}

    def step(self, action: IncidentAction) -> Tuple[IncidentObservation, float, bool, Dict[str, Any]]:
        self._state.steps_taken += 1
        self._set_last_action(action)

        if action.action_type == ActionType.INSPECT_LOGS:
            action_reward, info = self._reveal("logs")
            done = False
        elif action.action_type == ActionType.INSPECT_METRICS:
            action_reward, info = self._reveal("metrics")
            done = False
        elif action.action_type == ActionType.INSPECT_TRACES:
            action_reward, info = self._reveal("traces")
            done = False
        elif action.action_type == ActionType.INSPECT_DEPLOYS:
            action_reward, info = self._reveal("deploys")
            done = False
        elif action.action_type == ActionType.INSPECT_CONFIG:
            action_reward, info = self._reveal("config")
            done = False
        elif action.action_type == ActionType.INSPECT_CODE:
            action_reward, info = self._reveal("code")
            done = False
        elif action.action_type == ActionType.IDENTIFY_ROOT_CAUSE:
            action_reward, info = self._identify_root_cause(action.content)
            done = False
        elif action.action_type == ActionType.APPLY_FIX:
            action_reward, info = self._apply_fix(action.content)
            done = False
        elif action.action_type == ActionType.ROLLBACK_DEPLOY:
            action_reward, info = self._rollback_deploy()
            done = False
        elif action.action_type == ActionType.RESTART_SERVICE:
            action_reward, info = self._restart_service()
            done = False
        elif action.action_type == ActionType.SCALE_SERVICE:
            action_reward, info = self._scale_service()
            done = False
        elif action.action_type == ActionType.ADD_MONITOR:
            action_reward, info = self._add_monitor()
            done = False
        elif action.action_type == ActionType.RESOLVE_INCIDENT:
            action_reward, done, info = self._resolve_incident()
        else:
            self._state.last_action_error = "No action taken"
            action_reward = -0.05
            info = {"action_result": "no_change"}
            done = False

        self._sync_checks()
        if self._state.steps_taken >= self._state.max_steps:
            done = True
            if not self._state.service_restored:
                self._state.current_status = "timed_out"

        reward = self._compose_reward(action_reward)
        info.update(
            {
                "task_id": self.task.task_id,
                "difficulty": self.task.difficulty,
                "title": self.task.title,
                "last_action_error": self._state.last_action_error,
                "done_reason": (
                    "resolved" if self._state.current_status == "resolved" else "max_steps_reached" if self._state.steps_taken >= self._state.max_steps else "in_progress"
                ),
                "action_history": list(self.action_history),
            }
        )
        return self.state(), reward, done, info
