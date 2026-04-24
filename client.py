from __future__ import annotations

from typing import Optional

import requests

from models import (
    FrontendStoryTestPlan,
    FrontendSurfaceDiscovery,
    ProjectAgentConversationTrace,
    IncidentAction,
    IncidentObservation,
    MonitorIncidentTrigger,
    PredeployValidationResult,
    ProjectAgentCoordinationTrace,
    ProjectAgentRoster,
    ProjectCommandCenterSummary,
    ProjectEvent,
    ProjectLogBatchRequest,
    ProjectLogEntry,
    ProjectLogSummary,
    ProjectMetricBatchRequest,
    ProjectMetricPoint,
    ProjectMetricSummary,
    ProjectStoryReport,
    TestEnvironmentConfig,
    TestEnvironmentConfigRequest,
    TestEnvironmentRunRequest,
    TestEnvironmentRunResult,
    ProjectConfig,
    ProjectApiCheckRequest,
    ProjectBrowserCheckRequest,
    ProjectCreateRequest,
    IncidentRun,
    ProjectValidationSnapshot,
    RepoInspectionResult,
    RunTriageSummary,
    SessionInfo,
    SessionResetResponse,
    SessionStepResult,
    StepResult,
    UserStoryBatchCreateRequest,
    UserStoryExecutionResult,
    UserStoryRecord,
    WebsiteHealthSnapshot,
    WebsiteMonitorConfig,
    WebsiteMonitorUpdateRequest,
)


class OpenEnvClient:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def reset(self, task_id: str = "easy", max_steps: Optional[int] = None) -> IncidentObservation:
        payload = {"task_id": task_id, "max_steps": max_steps}
        response = requests.post(f"{self.base_url}/reset", json=payload, timeout=20)
        response.raise_for_status()
        return IncidentObservation.model_validate(response.json())

    def create_project(
        self,
        name: str,
        base_url: Optional[str] = None,
        repository_url: Optional[str] = None,
        healthcheck_path: str = "/health",
        metadata: Optional[dict[str, str]] = None,
        project_id: Optional[str] = None,
    ) -> ProjectConfig:
        payload = ProjectCreateRequest(
            project_id=project_id,
            name=name,
            base_url=base_url,
            repository_url=repository_url,
            healthcheck_path=healthcheck_path,
            metadata=metadata or {},
        ).model_dump(mode="json")
        response = requests.post(f"{self.base_url}/projects", json=payload, timeout=20)
        response.raise_for_status()
        return ProjectConfig.model_validate(response.json())

    def list_projects(self) -> list[ProjectConfig]:
        response = requests.get(f"{self.base_url}/projects", timeout=20)
        response.raise_for_status()
        return [ProjectConfig.model_validate(item) for item in response.json()]

    def set_project_monitor(
        self,
        project_id: str,
        base_url: str,
        healthcheck_path: str = "/health",
        expected_status: int = 200,
        timeout_seconds: float = 10.0,
        enabled: bool = True,
        headers: Optional[dict[str, str]] = None,
    ) -> WebsiteMonitorConfig:
        payload = WebsiteMonitorUpdateRequest(
            base_url=base_url,
            healthcheck_path=healthcheck_path,
            expected_status=expected_status,
            timeout_seconds=timeout_seconds,
            enabled=enabled,
            headers=headers or {},
        ).model_dump(mode="json")
        response = requests.put(f"{self.base_url}/projects/{project_id}/monitor", json=payload, timeout=20)
        response.raise_for_status()
        return WebsiteMonitorConfig.model_validate(response.json())

    def get_project_monitor(self, project_id: str) -> WebsiteMonitorConfig:
        response = requests.get(f"{self.base_url}/projects/{project_id}/monitor", timeout=20)
        response.raise_for_status()
        return WebsiteMonitorConfig.model_validate(response.json())

    def set_project_monitor_trigger(
        self,
        project_id: str,
        enabled: bool = True,
        failure_task_id: str = "easy",
        severity: str = "high",
        auto_create_run: bool = True,
    ) -> MonitorIncidentTrigger:
        payload = MonitorIncidentTrigger(
            enabled=enabled,
            failure_task_id=failure_task_id,
            severity=severity,
            auto_create_run=auto_create_run,
        ).model_dump(mode="json")
        response = requests.put(f"{self.base_url}/projects/{project_id}/monitor/trigger", json=payload, timeout=20)
        response.raise_for_status()
        return MonitorIncidentTrigger.model_validate(response.json())

    def get_project_monitor_trigger(self, project_id: str) -> MonitorIncidentTrigger:
        response = requests.get(f"{self.base_url}/projects/{project_id}/monitor/trigger", timeout=20)
        response.raise_for_status()
        return MonitorIncidentTrigger.model_validate(response.json())

    def check_project_monitor(self, project_id: str) -> WebsiteHealthSnapshot:
        response = requests.post(f"{self.base_url}/projects/{project_id}/monitor/check", timeout=20)
        response.raise_for_status()
        return WebsiteHealthSnapshot.model_validate(response.json())

    def get_project_health(self, project_id: str) -> WebsiteHealthSnapshot:
        response = requests.get(f"{self.base_url}/projects/{project_id}/health", timeout=20)
        response.raise_for_status()
        return WebsiteHealthSnapshot.model_validate(response.json())

    def run_project_api_check(
        self,
        project_id: str,
        path: str,
        method: str = "GET",
        expected_status: int = 200,
        timeout_seconds: float = 10.0,
        headers: Optional[dict[str, str]] = None,
        body: Optional[dict[str, object]] = None,
        label: Optional[str] = None,
    ) -> ProjectValidationSnapshot:
        payload = ProjectApiCheckRequest(
            method=method,
            path=path,
            expected_status=expected_status,
            timeout_seconds=timeout_seconds,
            headers=headers or {},
            body=body,
            label=label,
        ).model_dump(mode="json")
        response = requests.post(f"{self.base_url}/projects/{project_id}/checks/api", json=payload, timeout=20)
        response.raise_for_status()
        return ProjectValidationSnapshot.model_validate(response.json())

    def run_project_browser_check(
        self,
        project_id: str,
        path: str = "/",
        expected_text: Optional[str] = None,
        expected_selector: Optional[str] = None,
        timeout_seconds: float = 10.0,
        label: Optional[str] = None,
        browser_mode: str = "http",
        wait_until: str = "networkidle",
    ) -> ProjectValidationSnapshot:
        payload = ProjectBrowserCheckRequest(
            path=path,
            expected_text=expected_text,
            expected_selector=expected_selector,
            timeout_seconds=timeout_seconds,
            label=label,
            browser_mode=browser_mode,
            wait_until=wait_until,
        ).model_dump(mode="json")
        response = requests.post(f"{self.base_url}/projects/{project_id}/checks/browser", json=payload, timeout=20)
        response.raise_for_status()
        return ProjectValidationSnapshot.model_validate(response.json())

    def list_project_checks(self, project_id: str) -> list[ProjectValidationSnapshot]:
        response = requests.get(f"{self.base_url}/projects/{project_id}/checks", timeout=20)
        response.raise_for_status()
        return [ProjectValidationSnapshot.model_validate(item) for item in response.json()]

    def list_runs(self, project_id: Optional[str] = None) -> list[IncidentRun]:
        params = {"project_id": project_id} if project_id is not None else None
        response = requests.get(f"{self.base_url}/runs", params=params, timeout=20)
        response.raise_for_status()
        return [IncidentRun.model_validate(item) for item in response.json()]

    def create_project_stories(self, project_id: str, request: UserStoryBatchCreateRequest) -> list[UserStoryRecord]:
        response = requests.post(
            f"{self.base_url}/projects/{project_id}/stories",
            json=request.model_dump(mode="json"),
            timeout=20,
        )
        response.raise_for_status()
        return [UserStoryRecord.model_validate(item) for item in response.json()]

    def list_project_stories(self, project_id: str) -> list[UserStoryRecord]:
        response = requests.get(f"{self.base_url}/projects/{project_id}/stories", timeout=20)
        response.raise_for_status()
        return [UserStoryRecord.model_validate(item) for item in response.json()]

    def analyze_story(self, story_id: str) -> UserStoryRecord:
        response = requests.post(f"{self.base_url}/stories/{story_id}/analyze", timeout=20)
        response.raise_for_status()
        return UserStoryRecord.model_validate(response.json())

    def execute_story(self, story_id: str) -> UserStoryExecutionResult:
        response = requests.post(f"{self.base_url}/stories/{story_id}/execute", timeout=20)
        response.raise_for_status()
        return UserStoryExecutionResult.model_validate(response.json())

    def get_project_story_report(self, project_id: str) -> ProjectStoryReport:
        response = requests.get(f"{self.base_url}/projects/{project_id}/story-report", timeout=20)
        response.raise_for_status()
        return ProjectStoryReport.model_validate(response.json())

    def inspect_project_repository(self, project_id: str, query: str) -> RepoInspectionResult:
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/repo/inspect",
            params={"query": query},
            timeout=20,
        )
        response.raise_for_status()
        return RepoInspectionResult.model_validate(response.json())

    def discover_project_frontend(self, project_id: str) -> FrontendSurfaceDiscovery:
        response = requests.get(f"{self.base_url}/projects/{project_id}/frontend/discover", timeout=20)
        response.raise_for_status()
        return FrontendSurfaceDiscovery.model_validate(response.json())

    def get_story_code_context(self, story_id: str) -> RepoInspectionResult:
        response = requests.get(f"{self.base_url}/stories/{story_id}/code-context", timeout=20)
        response.raise_for_status()
        return RepoInspectionResult.model_validate(response.json())

    def get_story_frontend_plan(self, story_id: str) -> FrontendStoryTestPlan:
        response = requests.get(f"{self.base_url}/stories/{story_id}/frontend-plan", timeout=20)
        response.raise_for_status()
        return FrontendStoryTestPlan.model_validate(response.json())

    def add_project_logs(self, project_id: str, request: ProjectLogBatchRequest) -> list[ProjectLogEntry]:
        response = requests.post(
            f"{self.base_url}/projects/{project_id}/logs",
            json=request.model_dump(mode="json"),
            timeout=20,
        )
        response.raise_for_status()
        return [ProjectLogEntry.model_validate(item) for item in response.json()]

    def list_project_logs(self, project_id: str) -> list[ProjectLogEntry]:
        response = requests.get(f"{self.base_url}/projects/{project_id}/logs", timeout=20)
        response.raise_for_status()
        return [ProjectLogEntry.model_validate(item) for item in response.json()]

    def get_project_log_summary(self, project_id: str) -> ProjectLogSummary:
        response = requests.get(f"{self.base_url}/projects/{project_id}/logs/summary", timeout=20)
        response.raise_for_status()
        return ProjectLogSummary.model_validate(response.json())

    def add_project_metrics(self, project_id: str, request: ProjectMetricBatchRequest) -> list[ProjectMetricPoint]:
        response = requests.post(
            f"{self.base_url}/projects/{project_id}/metrics",
            json=request.model_dump(mode="json"),
            timeout=20,
        )
        response.raise_for_status()
        return [ProjectMetricPoint.model_validate(item) for item in response.json()]

    def list_project_metrics(self, project_id: str) -> list[ProjectMetricPoint]:
        response = requests.get(f"{self.base_url}/projects/{project_id}/metrics", timeout=20)
        response.raise_for_status()
        return [ProjectMetricPoint.model_validate(item) for item in response.json()]

    def get_project_metric_summary(self, project_id: str) -> ProjectMetricSummary:
        response = requests.get(f"{self.base_url}/projects/{project_id}/metrics/summary", timeout=20)
        response.raise_for_status()
        return ProjectMetricSummary.model_validate(response.json())

    def list_project_events(self, project_id: str, limit: int = 50) -> list[ProjectEvent]:
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/events",
            params={"limit": limit},
            timeout=20,
        )
        response.raise_for_status()
        return [ProjectEvent.model_validate(item) for item in response.json()]

    def get_project_summary(self, project_id: str) -> ProjectCommandCenterSummary:
        response = requests.get(f"{self.base_url}/projects/{project_id}/summary", timeout=20)
        response.raise_for_status()
        return ProjectCommandCenterSummary.model_validate(response.json())

    def get_project_agents(self, project_id: str) -> ProjectAgentRoster:
        response = requests.get(f"{self.base_url}/projects/{project_id}/agents", timeout=20)
        response.raise_for_status()
        return ProjectAgentRoster.model_validate(response.json())

    def get_project_agent_coordination(self, project_id: str, limit: int = 50) -> ProjectAgentCoordinationTrace:
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/agents/coordination",
            params={"limit": limit},
            timeout=20,
        )
        response.raise_for_status()
        return ProjectAgentCoordinationTrace.model_validate(response.json())

    def get_project_agent_conversation(self, project_id: str, limit: int = 50) -> ProjectAgentConversationTrace:
        response = requests.get(
            f"{self.base_url}/projects/{project_id}/agents/conversation",
            params={"limit": limit},
            timeout=20,
        )
        response.raise_for_status()
        return ProjectAgentConversationTrace.model_validate(response.json())

    def run_predeploy_validation(self, project_id: str, rerun_failed_only: bool = False) -> PredeployValidationResult:
        response = requests.post(
            f"{self.base_url}/projects/{project_id}/testing/predeploy",
            params={"rerun_failed_only": str(rerun_failed_only).lower()},
            timeout=60,
        )
        response.raise_for_status()
        return PredeployValidationResult.model_validate(response.json())

    def set_project_test_environment(self, project_id: str, request: TestEnvironmentConfigRequest) -> TestEnvironmentConfig:
        response = requests.put(
            f"{self.base_url}/projects/{project_id}/testing/environment",
            json=request.model_dump(mode="json"),
            timeout=20,
        )
        response.raise_for_status()
        return TestEnvironmentConfig.model_validate(response.json())

    def get_project_test_environment(self, project_id: str) -> TestEnvironmentConfig:
        response = requests.get(f"{self.base_url}/projects/{project_id}/testing/environment", timeout=20)
        response.raise_for_status()
        return TestEnvironmentConfig.model_validate(response.json())

    def run_project_test_environment(self, project_id: str, request: TestEnvironmentRunRequest) -> TestEnvironmentRunResult:
        response = requests.post(
            f"{self.base_url}/projects/{project_id}/testing/environment/run",
            json=request.model_dump(mode="json"),
            timeout=max(60, int(request.timeout_seconds) + 30),
        )
        response.raise_for_status()
        return TestEnvironmentRunResult.model_validate(response.json())

    def list_project_test_environment_runs(self, project_id: str) -> list[TestEnvironmentRunResult]:
        response = requests.get(f"{self.base_url}/projects/{project_id}/testing/environment/runs", timeout=20)
        response.raise_for_status()
        return [TestEnvironmentRunResult.model_validate(item) for item in response.json()]

    def create_session(self, task_id: str = "easy", max_steps: Optional[int] = None) -> SessionResetResponse:
        payload = {"task_id": task_id, "max_steps": max_steps}
        response = requests.post(f"{self.base_url}/sessions/reset", json=payload, timeout=20)
        response.raise_for_status()
        return SessionResetResponse.model_validate(response.json())

    def create_project_session(
        self,
        project_id: str,
        task_id: str = "easy",
        max_steps: Optional[int] = None,
    ) -> SessionResetResponse:
        payload = {"project_id": project_id, "task_id": task_id, "max_steps": max_steps}
        response = requests.post(f"{self.base_url}/sessions/reset", json=payload, timeout=20)
        response.raise_for_status()
        return SessionResetResponse.model_validate(response.json())

    def step(self, action_type: str, target: Optional[str] = None, content: Optional[str] = None) -> StepResult:
        payload = IncidentAction(action_type=action_type, target=target, content=content).model_dump(mode="json")
        response = requests.post(f"{self.base_url}/step", json=payload, timeout=20)
        response.raise_for_status()
        return StepResult.model_validate(response.json())

    def step_session(
        self,
        session_id: str,
        action_type: str,
        target: Optional[str] = None,
        content: Optional[str] = None,
    ) -> SessionStepResult:
        payload = {
            "session_id": session_id,
            "action": IncidentAction(action_type=action_type, target=target, content=content).model_dump(mode="json"),
        }
        response = requests.post(f"{self.base_url}/sessions/step", json=payload, timeout=20)
        response.raise_for_status()
        return SessionStepResult.model_validate(response.json())

    def state(self) -> IncidentObservation:
        response = requests.get(f"{self.base_url}/state", timeout=20)
        response.raise_for_status()
        return IncidentObservation.model_validate(response.json())

    def session_state(self, session_id: str) -> IncidentObservation:
        response = requests.get(f"{self.base_url}/sessions/{session_id}/state", timeout=20)
        response.raise_for_status()
        return IncidentObservation.model_validate(response.json())

    def get_session(self, session_id: str) -> SessionInfo:
        response = requests.get(f"{self.base_url}/sessions/{session_id}", timeout=20)
        response.raise_for_status()
        return SessionInfo.model_validate(response.json())

    def get_session_run(self, session_id: str) -> IncidentRun:
        response = requests.get(f"{self.base_url}/sessions/{session_id}/run", timeout=20)
        response.raise_for_status()
        return IncidentRun.model_validate(response.json())

    def triage_session(self, session_id: str) -> RunTriageSummary:
        response = requests.post(f"{self.base_url}/sessions/{session_id}/triage", timeout=20)
        response.raise_for_status()
        return RunTriageSummary.model_validate(response.json())

    def triage_run(self, run_id: str) -> RunTriageSummary:
        response = requests.post(f"{self.base_url}/runs/{run_id}/triage", timeout=20)
        response.raise_for_status()
        return RunTriageSummary.model_validate(response.json())
