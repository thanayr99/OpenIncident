from __future__ import annotations

from copy import deepcopy
import random
from typing import Any, Dict, List, Tuple
from uuid import uuid4

from models import IncidentAction, IncidentObservation, ActionType, IncidentTask
from tasks import TASK_REGISTRY


class ProductionIncidentEnv:
    def __init__(
        self,
        task_id: str = "easy",
        max_steps: int | None = None,
        *,
        stochastic_mode: str = "deterministic",
        dynamics_profile: str = "v1",
        random_seed: int | None = None,
    ) -> None:
        if task_id not in TASK_REGISTRY:
            raise ValueError(f"Unsupported task_id: {task_id}")
        if stochastic_mode not in {"deterministic", "stochastic"}:
            raise ValueError("stochastic_mode must be either 'deterministic' or 'stochastic'")
        if dynamics_profile not in {"v1", "v2"}:
            raise ValueError("dynamics_profile must be either 'v1' or 'v2'")
        self.task = TASK_REGISTRY[task_id].model_copy(deep=True)
        base_max_steps = max_steps or self.task.max_steps
        if max_steps is None and dynamics_profile == "v2":
            if task_id == "hard":
                base_max_steps += 3
            elif task_id == "medium":
                base_max_steps += 2
            else:
                base_max_steps += 1
        self.max_steps = base_max_steps
        self.stochastic_mode = stochastic_mode
        self.dynamics_profile = dynamics_profile
        self.random_seed = random_seed
        self._random = random.Random(random_seed)
        self.action_history: List[str] = []
        self._revealed: Dict[str, bool] = {}
        self._checks: Dict[str, bool] = {}
        self._external_context: Dict[str, Any] | None = None
        self._active_root_cause_keywords: List[str] = list(self.task.root_cause_keywords)
        self._active_valid_mitigations: List[str] = list(self.task.valid_mitigations)
        self._active_partial_mitigations: List[str] = list(self.task.partial_mitigations)
        self._active_harmful_actions: List[str] = list(self.task.harmful_actions)
        self._required_diagnosis_evidence: set[str] = set()
        self._scenario_label: str = "default"
        self._minimum_inspections_for_diagnosis = 0
        self._minimum_inspections_for_fix = 0
        self._pending_recovery_verification = False
        self._fix_expected_to_restore = False
        self._fix_failure_rate = 0.0
        self._verification_required_signals: set[str] = set()
        self._verification_completed_signals: set[str] = set()
        self._state = self._build_initial_state()

    def _sample_episode_profile(self) -> None:
        self._active_root_cause_keywords = list(self.task.root_cause_keywords)
        self._active_valid_mitigations = list(self.task.valid_mitigations)
        self._active_partial_mitigations = list(self.task.partial_mitigations)
        self._active_harmful_actions = list(self.task.harmful_actions)
        self._required_diagnosis_evidence = set()
        self._scenario_label = "default"
        self._minimum_inspections_for_diagnosis = 0
        self._minimum_inspections_for_fix = 0
        self._pending_recovery_verification = False
        self._fix_expected_to_restore = False
        self._fix_failure_rate = 0.0
        self._verification_required_signals = set()
        self._verification_completed_signals = set()

        if self.stochastic_mode != "stochastic":
            return

        if self.dynamics_profile == "v1":
            evidence_pool = ["logs", "metrics", "traces", "deploys", "config", "code"]
            evidence_count = min(2, len(evidence_pool))
            sampled_evidence = set(self._random.sample(evidence_pool, k=evidence_count))
            sampled_keywords = self._random.sample(
                self.task.root_cause_keywords,
                k=max(1, min(2, len(self.task.root_cause_keywords))),
            )
            sampled_valid_mitigation = self._random.sample(
                self.task.valid_mitigations,
                k=max(1, min(2, len(self.task.valid_mitigations))),
            )
            remaining_valid = [item for item in self.task.valid_mitigations if item not in sampled_valid_mitigation]

            self._required_diagnosis_evidence = sampled_evidence
            self._active_root_cause_keywords = sampled_keywords
            self._active_valid_mitigations = sampled_valid_mitigation
            self._active_partial_mitigations = list(self.task.partial_mitigations) + remaining_valid
            self._active_harmful_actions = list(self.task.harmful_actions)
            self._scenario_label = f"variant-{self._random.randint(1, 999):03d}"
            self._minimum_inspections_for_diagnosis = 1
            self._minimum_inspections_for_fix = 1
            self._fix_failure_rate = 0.14
            return

        evidence_pool = ["logs", "metrics", "traces", "deploys", "config", "code"]
        evidence_count = min(len(evidence_pool), self._random.randint(2, 3))
        sampled_evidence = set(self._random.sample(evidence_pool, k=evidence_count))
        keyword_sample_size = max(2, min(3, len(self.task.root_cause_keywords)))
        mitigation_sample_size = max(2, min(3, len(self.task.valid_mitigations)))
        sampled_keywords = self._random.sample(
            self.task.root_cause_keywords,
            k=keyword_sample_size,
        )
        sampled_valid_mitigation = self._random.sample(
            self.task.valid_mitigations,
            k=mitigation_sample_size,
        )
        remaining_valid = [item for item in self.task.valid_mitigations if item not in sampled_valid_mitigation]
        partial_candidates = list(dict.fromkeys(list(self.task.partial_mitigations) + remaining_valid))
        verification_pool = ["logs", "metrics", "traces", "deploys"]
        verification_count = 2 if self.task.task_id == "hard" else 1
        verification_count = min(verification_count, len(verification_pool))

        self._required_diagnosis_evidence = sampled_evidence
        self._active_root_cause_keywords = sampled_keywords
        self._active_valid_mitigations = sampled_valid_mitigation
        self._active_partial_mitigations = partial_candidates
        self._active_harmful_actions = list(self.task.harmful_actions)
        self._scenario_label = f"v2-{self.task.task_id}-{self._random.randint(100, 999)}"
        if self.task.task_id == "hard":
            self._minimum_inspections_for_diagnosis = 2
            self._minimum_inspections_for_fix = 2
            self._fix_failure_rate = 0.20
        elif self.task.task_id == "medium":
            self._minimum_inspections_for_diagnosis = 2
            self._minimum_inspections_for_fix = 2
            self._fix_failure_rate = 0.15
        else:
            self._minimum_inspections_for_diagnosis = 1
            self._minimum_inspections_for_fix = 1
            self._fix_failure_rate = 0.10
        self._verification_required_signals = set(self._random.sample(verification_pool, k=verification_count))

    def _apply_initial_noise(self, state: IncidentObservation) -> None:
        if self.stochastic_mode != "stochastic":
            return
        for metric_name, metric_value in list(state.metrics.items()):
            jitter = self._random.uniform(0.85, 1.20)
            state.metrics[metric_name] = round(metric_value * jitter, 3)
        reliability_jitter = self._random.uniform(-4.5, 4.5)
        state.reliability_score = round(max(0.0, min(100.0, state.reliability_score + reliability_jitter)), 2)
        if self._required_diagnosis_evidence:
            state.investigation_notes.append(
                "Incident variant requires evidence from "
                + ", ".join(sorted(self._required_diagnosis_evidence))
                + " before diagnosis is considered reliable."
            )
        if self.dynamics_profile == "v2":
            state.investigation_notes.append(
                "V2 workflow enforced: inspect -> diagnose -> fix -> verify -> resolve."
            )

    def _inspection_count(self) -> int:
        return sum(1 for revealed in self._revealed.values() if revealed)

    def _current_action_streak(self) -> tuple[str | None, int]:
        if not self.action_history:
            return None, 0
        last = self.action_history[-1]
        streak = 0
        for action_name in reversed(self.action_history):
            if action_name != last:
                break
            streak += 1
        return last, streak

    def _has_required_diagnosis_evidence(self) -> bool:
        if not self._required_diagnosis_evidence:
            return True
        if self.dynamics_profile == "v2":
            required_count = len(self._required_diagnosis_evidence)
            covered_count = sum(1 for kind in self._required_diagnosis_evidence if self._revealed.get(kind, False))
            threshold = max(1, required_count // 2)
            return covered_count >= threshold
        return any(self._revealed.get(kind, False) for kind in self._required_diagnosis_evidence)

    def _build_initial_state(self) -> IncidentObservation:
        self.action_history = []
        self._sample_episode_profile()
        self._revealed = {
            "logs": False,
            "metrics": False,
            "traces": False,
            "deploys": False,
            "config": False,
            "code": False,
        }
        self._checks = {check_name: False for check_name in self.task.expected_checks}
        self._external_context = None
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
        self._apply_initial_noise(state)
        return state

    def reset(self) -> IncidentObservation:
        self._state = self._build_initial_state()
        return self.state()

    def prepare_external_incident(
        self,
        *,
        project_name: str,
        trigger_reason: str,
        severity: str | None = None,
        repository_url: str | None = None,
        base_url: str | None = None,
    ) -> IncidentObservation:
        self.action_history = []
        self._active_root_cause_keywords = list(self.task.root_cause_keywords)
        self._active_valid_mitigations = list(self.task.valid_mitigations)
        self._active_partial_mitigations = list(self.task.partial_mitigations)
        self._active_harmful_actions = list(self.task.harmful_actions)
        self._required_diagnosis_evidence = set()
        self._scenario_label = "external"
        self._minimum_inspections_for_diagnosis = 0
        self._minimum_inspections_for_fix = 0
        self._pending_recovery_verification = False
        self._fix_expected_to_restore = False
        self._fix_failure_rate = 0.0
        self._verification_required_signals = set()
        self._verification_completed_signals = set()
        self._revealed = {
            "logs": False,
            "metrics": False,
            "traces": False,
            "deploys": False,
            "config": False,
            "code": False,
        }
        self._checks = {check_name: False for check_name in self.task.expected_checks}
        self._external_context = {
            "project_name": project_name,
            "repository_url": repository_url,
            "base_url": base_url,
        }
        self._state = IncidentObservation(
            incident_id=f"external-{uuid4().hex[:12]}",
            difficulty="external",
            service_name=project_name,
            incident_summary=f"External incident detected for {project_name}. {trigger_reason}",
            current_status="investigating",
            severity=severity or self.task.severity,
            user_impact=f"Users may be affected because {project_name} is failing validation checks.",
            logs=[],
            metrics={},
            traces=[],
            recent_deploys=[],
            config_snapshot={},
            code_snippet="",
            available_dashboards=["website-health", "api-validation", "browser-checks"],
            investigation_notes=["Incident created from external monitoring or validation evidence."],
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
        return self.state()

    def attach_external_signal(
        self,
        *,
        project_name: str,
        target_url: str,
        status: str,
        check_type: str = "health",
        label: str | None = None,
        status_code: int | None = None,
        response_time_ms: float | None = None,
        error_message: str | None = None,
        response_excerpt: str | None = None,
    ) -> IncidentObservation:
        label_text = label or check_type
        summary = f"{label_text.capitalize()} signal for {project_name} reported {status} on {target_url}."
        if self._state.incident_summary:
            self._state.incident_summary = f"{self._state.incident_summary} {summary}"
        else:
            self._state.incident_summary = summary

        self._add_note(f"{label_text.capitalize()} detected {status} at {target_url}.")
        if response_time_ms is not None:
            self._state.metrics[f"{check_type}_response_time_ms"] = response_time_ms
        if status_code is not None:
            self._state.metrics[f"{check_type}_status_code"] = float(status_code)

        log_line = f"{check_type.upper()} status={status} url={target_url}"
        if status_code is not None:
            log_line += f" status_code={status_code}"
        if response_time_ms is not None:
            log_line += f" response_time_ms={response_time_ms}"
        self._state.logs.append(log_line)

        if error_message:
            self._state.logs.append(f"{check_type.upper()} error={error_message}")
            self._state.last_action_error = error_message
        if response_excerpt:
            self._state.logs.append(f"{check_type.upper()} response_excerpt={response_excerpt}")

        self._state.user_impact = f"Users may be affected because {project_name} is reporting a {status} {label_text} signal."
        return self.state()

    def mark_recovered_from_signal(
        self,
        *,
        project_name: str,
        target_url: str,
        check_type: str,
        label: str | None = None,
        status_code: int | None = None,
        response_time_ms: float | None = None,
    ) -> IncidentObservation:
        label_text = label or check_type
        self._state.current_status = "resolved"
        self._state.service_restored = True
        self._state.mitigation_applied = True
        self._state.last_action_error = None
        self._state.suspected_root_cause = self._state.suspected_root_cause or f"{label_text} recovered before manual intervention."
        self._add_note(f"{label_text.capitalize()} recovered at {target_url}.")
        self._state.logs.append(f"{check_type.upper()} recovered url={target_url}")
        if status_code is not None:
            self._state.metrics[f"{check_type}_status_code"] = float(status_code)
        if response_time_ms is not None:
            self._state.metrics[f"{check_type}_response_time_ms"] = response_time_ms
        self._state.user_impact = f"{project_name} appears healthy again based on the latest {label_text} signal."
        self._mark_restored_checks()
        self._bump_reliability(18)
        return self.state()

    def attach_test_environment_context(
        self,
        *,
        workspace_path: str,
        install_command: str | None = None,
        test_command: str | None = None,
        install_stdout: str | None = None,
        install_stderr: str | None = None,
        test_stdout: str | None = None,
        test_stderr: str | None = None,
    ) -> IncidentObservation:
        self._add_note(f"Testing environment workspace: {workspace_path}.")
        if install_command:
            self._state.logs.append(f"TEST_ENV install_command={install_command}")
        if test_command:
            self._state.logs.append(f"TEST_ENV test_command={test_command}")
        if install_stdout:
            self._state.logs.append(f"TEST_ENV install_stdout={install_stdout[:300]}")
        if install_stderr:
            self._state.logs.append(f"TEST_ENV install_stderr={install_stderr[:300]}")
        if test_stdout:
            self._state.logs.append(f"TEST_ENV test_stdout={test_stdout[:300]}")
        if test_stderr:
            self._state.logs.append(f"TEST_ENV test_stderr={test_stderr[:300]}")
        return self.state()

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any]) -> "ProductionIncidentEnv":
        env = cls(
            task_id=snapshot["task_id"],
            max_steps=snapshot.get("max_steps"),
            stochastic_mode=snapshot.get("stochastic_mode", "deterministic"),
            dynamics_profile=snapshot.get("dynamics_profile", "v1"),
            random_seed=snapshot.get("random_seed"),
        )
        env.action_history = list(snapshot.get("action_history", []))
        env._revealed = dict(snapshot.get("revealed", env._revealed))
        env._checks = dict(snapshot.get("checks", env._checks))
        env._external_context = snapshot.get("external_context")
        env._active_root_cause_keywords = list(snapshot.get("active_root_cause_keywords", env._active_root_cause_keywords))
        env._active_valid_mitigations = list(snapshot.get("active_valid_mitigations", env._active_valid_mitigations))
        env._active_partial_mitigations = list(snapshot.get("active_partial_mitigations", env._active_partial_mitigations))
        env._active_harmful_actions = list(snapshot.get("active_harmful_actions", env._active_harmful_actions))
        env._required_diagnosis_evidence = set(snapshot.get("required_diagnosis_evidence", []))
        env._scenario_label = str(snapshot.get("scenario_label", env._scenario_label))
        env._minimum_inspections_for_diagnosis = int(
            snapshot.get("minimum_inspections_for_diagnosis", env._minimum_inspections_for_diagnosis)
        )
        env._minimum_inspections_for_fix = int(snapshot.get("minimum_inspections_for_fix", env._minimum_inspections_for_fix))
        env._pending_recovery_verification = bool(
            snapshot.get("pending_recovery_verification", env._pending_recovery_verification)
        )
        env._fix_expected_to_restore = bool(snapshot.get("fix_expected_to_restore", env._fix_expected_to_restore))
        env._fix_failure_rate = float(snapshot.get("fix_failure_rate", env._fix_failure_rate))
        env._verification_required_signals = set(snapshot.get("verification_required_signals", []))
        env._verification_completed_signals = set(snapshot.get("verification_completed_signals", []))
        env._state = IncidentObservation.model_validate(snapshot["state"])
        return env

    def state(self) -> IncidentObservation:
        return self._state.model_copy(deep=True)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "task_id": self.task.task_id,
            "max_steps": self.max_steps,
            "stochastic_mode": self.stochastic_mode,
            "dynamics_profile": self.dynamics_profile,
            "random_seed": self.random_seed,
            "action_history": list(self.action_history),
            "revealed": deepcopy(self._revealed),
            "checks": deepcopy(self._checks),
            "external_context": deepcopy(self._external_context),
            "active_root_cause_keywords": list(self._active_root_cause_keywords),
            "active_valid_mitigations": list(self._active_valid_mitigations),
            "active_partial_mitigations": list(self._active_partial_mitigations),
            "active_harmful_actions": list(self._active_harmful_actions),
            "required_diagnosis_evidence": sorted(self._required_diagnosis_evidence),
            "scenario_label": self._scenario_label,
            "minimum_inspections_for_diagnosis": self._minimum_inspections_for_diagnosis,
            "minimum_inspections_for_fix": self._minimum_inspections_for_fix,
            "pending_recovery_verification": self._pending_recovery_verification,
            "fix_expected_to_restore": self._fix_expected_to_restore,
            "fix_failure_rate": self._fix_failure_rate,
            "verification_required_signals": sorted(self._verification_required_signals),
            "verification_completed_signals": sorted(self._verification_completed_signals),
            "state": self._state.model_dump(mode="json"),
        }

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

    def _verify_pending_recovery(self, evidence_kind: str) -> float:
        if not self._pending_recovery_verification:
            return 0.0
        if evidence_kind not in {"logs", "metrics", "traces", "deploys"}:
            return 0.0

        if self.dynamics_profile == "v2" and self._verification_required_signals:
            if evidence_kind in self._verification_completed_signals:
                self._state.last_action_error = f"{evidence_kind} already used for recovery verification"
                self._bump_reliability(-2)
                return -0.03

            self._verification_completed_signals.add(evidence_kind)
            remaining = self._verification_required_signals - self._verification_completed_signals
            if remaining:
                self._add_note(
                    "Recovery verification progress: remaining signals "
                    + ", ".join(sorted(remaining))
                )
                self._sync_checks()
                return 0.04 if self._fix_expected_to_restore else -0.04

        self._pending_recovery_verification = False
        if self._fix_expected_to_restore:
            self._state.service_restored = True
            self._state.current_status = "mitigated"
            self._state.last_action_error = None
            self._add_note(f"Fix effectiveness verified through {evidence_kind}.")
            self._mark_restored_checks()
            self._bump_reliability(12)
            self._update_recovered_metrics()
            return 0.16

        self._state.current_status = "degraded"
        self._state.last_action_error = "Verification showed the applied fix did not restore service"
        self._add_note("Verification failed; mitigation must be revised.")
        self._bump_reliability(-7)
        self._sync_checks()
        return -0.08

    def _reveal(self, kind: str) -> Tuple[float, Dict[str, Any]]:
        was_revealed = self._revealed[kind]
        allow_repeat_for_verification = self._pending_recovery_verification and self.stochastic_mode == "stochastic"
        if was_revealed and not allow_repeat_for_verification:
            self._state.last_action_error = f"{kind} already inspected"
            self._bump_reliability(-2)
            return -0.01, {"action_result": "redundant_inspection"}

        self._revealed[kind] = True
        verification_reward = self._verify_pending_recovery(kind)
        if self._external_context is not None:
            project_name = self._external_context.get("project_name", "project")
            repository_url = self._external_context.get("repository_url")
            base_url = self._external_context.get("base_url")
            if kind == "logs":
                self._state.logs.append(f"LOG CONNECTOR pending for {project_name}; currently using website validation evidence only.")
                self._add_note("No runtime log integration is configured yet for this project.")
            elif kind == "metrics":
                if base_url:
                    self._state.metrics["website_checks_configured"] = 1.0
                self._add_note("No observability metrics connector is configured yet for this project.")
            elif kind == "traces":
                self._state.traces.append("Trace connector not configured yet; no distributed trace data available.")
                self._add_note("Tracing is not connected for this project yet.")
            elif kind == "deploys":
                if repository_url:
                    self._state.recent_deploys = [f"Repository linked: {repository_url}"]
                else:
                    self._state.recent_deploys = ["No deployment integration configured yet."]
                self._add_note("Deployment history needs a CI/CD or hosting connector.")
            elif kind == "config":
                self._state.config_snapshot = {"integration_status": "Runtime configuration connector not configured yet."}
                self._add_note("Runtime config is not available until a config/source-of-truth connector is added.")
            else:
                self._state.code_snippet = (
                    f"# Code inspection is not connected yet for {project_name}.\n"
                    "# Link the repository integration to inspect source files here."
                )
                self._add_note("Repository-aware code inspection is not configured yet.")
            base_reward = 0.01 if not was_revealed else -0.005
            action_result = f"revealed_{kind}_placeholder" if not was_revealed else f"rechecked_{kind}_placeholder"
            return base_reward + verification_reward, {"action_result": action_result}

        if kind == "logs" and not was_revealed:
            self._state.logs.extend(self.task.hidden_logs)
            self._add_note("Expanded log context reviewed.")
            reward = 0.02
        elif kind == "metrics" and not was_revealed:
            self._state.metrics.update(self.task.hidden_metrics)
            self._add_note("Deep metrics checked for incident impact.")
            reward = 0.02
        elif kind == "traces" and not was_revealed:
            self._state.traces.extend(self.task.hidden_traces)
            self._add_note("Request traces inspected.")
            reward = 0.03
        elif kind == "deploys" and not was_revealed:
            self._state.recent_deploys = deepcopy(self.task.recent_deploys)
            self._add_note("Recent deploy history inspected.")
            reward = 0.02
        elif kind == "config" and not was_revealed:
            self._state.config_snapshot = deepcopy(self.task.config_snapshot)
            self._add_note("Runtime configuration inspected.")
            reward = 0.02
        elif kind == "code" and not was_revealed:
            self._state.code_snippet = self.task.code_snippet
            self._add_note("Relevant code path inspected.")
            reward = 0.03
        else:
            reward = -0.005

        if self.dynamics_profile == "v2" and not was_revealed and kind in self._required_diagnosis_evidence:
            reward += 0.02
            self._add_note(f"Required diagnosis signal captured from {kind}.")

        action_result = f"revealed_{kind}" if not was_revealed else f"rechecked_{kind}"
        return reward + verification_reward, {"action_result": action_result}

    def _identify_root_cause(self, content: str | None) -> Tuple[float, Dict[str, Any]]:
        if self.stochastic_mode == "stochastic":
            if self._inspection_count() < self._minimum_inspections_for_diagnosis:
                self._state.suspected_root_cause = content
                self._state.last_action_error = "Diagnosis attempted before collecting enough evidence"
                self._bump_reliability(-6)
                if self.dynamics_profile == "v2":
                    self._add_note("Next step: inspect logs/metrics/traces before diagnosis.")
                self._sync_checks()
                penalty = -0.12 if self.dynamics_profile == "v2" else -0.16
                return penalty, {"action_result": "diagnosis_insufficient_evidence"}
            if not self._has_required_diagnosis_evidence():
                self._state.suspected_root_cause = content
                self._state.last_action_error = (
                    "Diagnosis missing required signal coverage: "
                    + ", ".join(sorted(self._required_diagnosis_evidence))
                )
                self._bump_reliability(-6)
                if self.dynamics_profile == "v2":
                    self._add_note(
                        "Next step: cover required diagnosis signals: "
                        + ", ".join(sorted(self._required_diagnosis_evidence))
                    )
                self._sync_checks()
                penalty = -0.10 if self.dynamics_profile == "v2" else -0.14
                return penalty, {"action_result": "diagnosis_missing_required_signals"}

        if self._matches_any(content, self._active_root_cause_keywords):
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
        if self.stochastic_mode == "stochastic" and not self._state.root_cause_confirmed:
            self._state.last_action_error = "Mitigation attempted before confirming root cause"
            self._bump_reliability(-8)
            if self.dynamics_profile == "v2":
                self._add_note("Next step: confirm root cause before applying fix.")
            self._sync_checks()
            penalty = -0.15 if self.dynamics_profile == "v2" else -0.22
            return penalty, {"action_result": "fix_before_diagnosis"}
        if self.stochastic_mode == "stochastic" and self._inspection_count() < self._minimum_inspections_for_fix:
            self._state.last_action_error = "Mitigation attempted before enough investigation context was collected"
            self._bump_reliability(-6)
            if self.dynamics_profile == "v2":
                self._add_note("Next step: gather one more investigation signal, then apply fix.")
            self._sync_checks()
            penalty = -0.10 if self.dynamics_profile == "v2" else -0.14
            return penalty, {"action_result": "fix_insufficient_context"}

        if self._matches_any(normalized, self._active_valid_mitigations):
            if self.stochastic_mode == "stochastic":
                evidence_bonus = 0.12 if self._has_required_diagnosis_evidence() else -0.10
                success_probability = min(0.92, max(0.25, 0.68 + evidence_bonus - self._fix_failure_rate))
                self._state.mitigation_applied = True
                self._state.current_status = "mitigation_pending_verification"
                self._add_note("Fix applied. Verification step required before resolving incident.")
                self._pending_recovery_verification = True
                self._fix_expected_to_restore = self._random.random() < success_probability
                self._verification_completed_signals = set()
                self._sync_checks()
                return 0.14, {"action_result": "mitigation_pending_verification"}
            self._apply_valid_fix("Full mitigation applied successfully.")
            return 0.30, {"action_result": "full_mitigation"}
        if self._matches_any(normalized, self._active_partial_mitigations):
            self._apply_partial_fix("Partial mitigation reduced impact but did not fully recover service.")
            return 0.12, {"action_result": "partial_mitigation"}
        if self._matches_any(normalized, self._active_harmful_actions):
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
        if self._pending_recovery_verification:
            self._state.last_action_error = "Resolve blocked: verify fix outcome via logs/metrics/traces first"
            self._bump_reliability(-6)
            return -0.18, False, {"action_result": "resolve_without_verification"}
        if self.dynamics_profile == "v2" and self.task.difficulty == "hard" and not self._state.monitoring_added:
            self._state.last_action_error = "Resolve blocked: add monitor after restoration before closure"
            self._bump_reliability(-4)
            return -0.09, False, {"action_result": "resolve_without_monitor"}
        if self._state.service_restored and self._state.root_cause_confirmed:
            self._state.current_status = "resolved"
            self._add_note("Incident resolved after service restoration.")
            self._sync_checks()
            return 0.10, True, {"action_result": "incident_resolved"}
        if self._state.service_restored and not self._state.root_cause_confirmed:
            self._state.last_action_error = "Cannot resolve incident before confirming the root cause"
            self._bump_reliability(-6)
            return -0.12, False, {"action_result": "resolve_without_diagnosis"}
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

        repeat_penalty_applied = False
        streak_action, streak_count = self._current_action_streak()
        if self.dynamics_profile == "v2" and streak_count >= 3 and streak_action in {
            ActionType.IDENTIFY_ROOT_CAUSE.value,
            ActionType.APPLY_FIX.value,
            ActionType.RESOLVE_INCIDENT.value,
        }:
            action_reward -= 0.05
            repeat_penalty_applied = True
            self._add_note(f"Repeated action '{streak_action}' reduced effectiveness; diversify investigation steps.")

        reward = self._compose_reward(action_reward)
        info.update(
            {
                "task_id": self.task.task_id,
                "difficulty": self.task.difficulty,
                "stochastic_mode": self.stochastic_mode,
                "dynamics_profile": self.dynamics_profile,
                "scenario_label": self._scenario_label,
                "pending_recovery_verification": self._pending_recovery_verification,
                "verification_required_signals": sorted(self._verification_required_signals),
                "verification_completed_signals": sorted(self._verification_completed_signals),
                "required_diagnosis_evidence": sorted(self._required_diagnosis_evidence),
                "minimum_inspections_for_diagnosis": self._minimum_inspections_for_diagnosis,
                "minimum_inspections_for_fix": self._minimum_inspections_for_fix,
                "action_streak_count": streak_count,
                "repeat_penalty_applied": repeat_penalty_applied,
                "title": self.task.title,
                "last_action_error": self._state.last_action_error,
                "done_reason": (
                    "resolved" if self._state.current_status == "resolved" else "max_steps_reached" if self._state.steps_taken >= self._state.max_steps else "in_progress"
                ),
                "action_history": list(self.action_history),
            }
        )
        return self.state(), reward, done, info
