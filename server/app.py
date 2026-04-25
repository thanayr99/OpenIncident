from __future__ import annotations

from datetime import datetime, timezone
import os
import subprocess
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import requests

from models import (
    AgentTrainingPlan,
    AuthAccount,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthRegisterRequest,
    DatabaseMigrationStatus,
    DatabaseOverview,
    DatabaseRowView,
    DatabaseTableRows,
    FrontendStoryTestPlan,
    FrontendSurfaceDiscovery,
    AgentRole,
    ProjectAgentConversationTrace,
    ProjectAgentRoster,
    ProjectAgentCoordinationTrace,
    IncidentAction,
    IncidentObservation,
    MonitorIncidentTrigger,
    PredeployValidationResult,
    ProjectCommandCenterSummary,
    ProjectEvent,
    ProjectLogBatchRequest,
    ProjectLogConnectorConfig,
    ProjectLogConnectorPullRequest,
    ProjectLogConnectorPullResult,
    ProjectLogConnectorRequest,
    ProjectLogEntry,
    ProjectLogSummary,
    ProjectMetricBatchRequest,
    ProjectMetricPoint,
    ProjectMetricSummary,
    ProjectEndpoint,
    ProjectEndpointBatchUpdateRequest,
    ProjectConfig,
    ProjectApiCheckRequest,
    ProjectBrowserCheckRequest,
    ProjectCreateRequest,
    ProjectDiagnosticIssue,
    ProjectDiagnosticSweepResult,
    ProjectApiTrainingDataset,
    ProjectEnvironmentSummary,
    ProjectFrontendTrainingDataset,
    ProjectGuardianTrainingDataset,
    ProjectObservabilityTrainingDataset,
    ProjectOversightTrainingDataset,
    ProjectStoryReport,
    ProjectPlannerSummary,
    ProjectPlannerTrainingDataset,
    ProjectTriageTrainingDataset,
    IncidentRun,
    RepoInspectionResult,
    RunTriageSummary,
    SessionResetRequest,
    SessionResetResponse,
    SessionInfo,
    SessionExecutionPolicy,
    SessionExecutionPolicyUpdateRequest,
    SessionStepRequest,
    SessionStepResult,
    StoryDomain,
    StoryStatus,
    StepResult,
    ProjectValidationSnapshot,
    TestEnvironmentConfig,
    TestEnvironmentConfigRequest,
    TestEnvironmentRunRequest,
    TestEnvironmentRunResult,
    UserStoryBatchCreateRequest,
    UserStoryExecutionResult,
    UserStoryRecord,
    WebsiteHealthSnapshot,
    WebsiteMonitorConfig,
    WebsiteMonitorUpdateRequest,
)
from server.agent_training import build_agent_training_plan
from server.browser_checks import run_http_browser_check, run_playwright_browser_check
from server.config import get_allowed_origins, get_api_port, get_database_target
from server.environment import ProductionIncidentEnv
from server.github_repo import (
    build_frontend_story_plan,
    discover_frontend_surface,
    inspect_repository_for_query,
    inspect_repository_for_story,
)
from server.session_store import InMemorySessionStore
from server.story_engine import execute_api_story, execute_frontend_story
from server.test_environment import run_test_environment
from server.triage import build_run_triage


def _story_result_to_snapshot(result: UserStoryExecutionResult, story: UserStoryRecord) -> ProjectValidationSnapshot | None:
    if result.test_type.value not in {"browser", "api", "health"}:
        return None

    output = result.output or {}
    target_url = output.get("target_url")
    if not target_url:
        return None

    return ProjectValidationSnapshot(
        project_id=result.project_id,
        endpoint_id=output.get("endpoint_id"),
        endpoint_label=output.get("endpoint_label"),
        endpoint_surface=output.get("endpoint_surface"),
        check_type=result.test_type.value,
        label=story.title,
        target_url=target_url,
        status="unhealthy" if result.status == StoryStatus.FAILED else "healthy",
        status_code=output.get("status_code"),
        response_time_ms=output.get("response_time_ms"),
        error_message=output.get("error_message") or result.summary,
        response_excerpt=output.get("response_excerpt"),
        engine=output.get("engine", result.test_type.value),
        observed_url=output.get("observed_url"),
        page_title=output.get("page_title"),
    )


def _resolve_project_endpoint(
    project: ProjectConfig,
    *,
    endpoint_id: str | None = None,
    preferred_surface: str | None = None,
):
    try:
        return session_store.resolve_project_endpoint(
            project.project_id,
            endpoint_id=endpoint_id,
            preferred_surface=preferred_surface,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _log_issue(
    issues: list[ProjectDiagnosticIssue],
    *,
    severity: str,
    category: str,
    title: str,
    detail: str,
) -> None:
    issues.append(
        ProjectDiagnosticIssue(
            severity=severity,
            category=category,
            title=title,
            detail=detail,
        )
    )


def _build_log_findings(log_summary: ProjectLogSummary | None) -> tuple[list[str], list[ProjectDiagnosticIssue]]:
    findings: list[str] = []
    issues: list[ProjectDiagnosticIssue] = []
    if log_summary is None:
        _log_issue(
            issues,
            severity="warning",
            category="logs",
            title="Log summary unavailable",
            detail="Runtime logs could not be summarized for this project.",
        )
        return findings, issues

    if log_summary.total_entries == 0:
        _log_issue(
            issues,
            severity="warning",
            category="logs",
            title="No runtime logs connected",
            detail="Connect runtime logs to improve diagnosis confidence and root-cause evidence.",
        )
        return findings, issues

    findings.append(f"Total log entries: {log_summary.total_entries}")
    findings.append(f"Error entries: {log_summary.error_entries}")
    findings.append(f"Warning entries: {log_summary.warning_entries}")
    if log_summary.top_signals:
        findings.append(f"Top signals: {', '.join(log_summary.top_signals[:5])}")
    if log_summary.latest_errors:
        findings.extend(log_summary.latest_errors[:3])

    if log_summary.error_entries > 0:
        _log_issue(
            issues,
            severity="error",
            category="logs",
            title="Runtime errors detected",
            detail=f"Detected {log_summary.error_entries} error log entr{'y' if log_summary.error_entries == 1 else 'ies'}.",
        )
    if log_summary.warning_entries > 0:
        _log_issue(
            issues,
            severity="warning",
            category="logs",
            title="Runtime warnings detected",
            detail=f"Detected {log_summary.warning_entries} warning log entr{'y' if log_summary.warning_entries == 1 else 'ies'}.",
        )
    return findings, issues


app = FastAPI(title="Production Incident Debugging Environment", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
session_store = InMemorySessionStore()
default_session, _, environment = session_store.create_session(persist=False)
STATIC_DIR = Path(__file__).resolve().parent / "static"
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="frontend-assets")


def _dashboard_entrypoint() -> Path:
    built_index = FRONTEND_DIST_DIR / "index.html"
    if built_index.exists():
        return built_index
    return STATIC_DIR / "index.html"


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    value = authorization.strip()
    if not value:
        return None
    if not value.lower().startswith("bearer "):
        return None
    token = value.split(" ", 1)[1].strip()
    return token or None


def _require_account_from_header(authorization: str | None) -> AuthAccount:
    token = _extract_bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    try:
        return session_store.get_account_from_token(token)
    except KeyError as exc:
        raise HTTPException(status_code=401, detail="Authentication required") from exc


def _optional_account_from_header(authorization: str | None) -> AuthAccount | None:
    token = _extract_bearer_token(authorization)
    if authorization is not None and token is None:
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    if token is None:
        return None
    try:
        return session_store.get_account_from_token(token)
    except KeyError as exc:
        raise HTTPException(status_code=401, detail="Authentication required") from exc


def _ensure_project_access(project: ProjectConfig, account: AuthAccount | None) -> None:
    owner_id = project.metadata.get("owner_id")
    if not owner_id:
        return
    if account is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if account.account_id != owner_id:
        raise HTTPException(status_code=403, detail="Forbidden: project access denied")


def _require_project_access(
    project_id: str,
    authorization: str | None,
) -> tuple[ProjectConfig, AuthAccount | None]:
    account = _optional_account_from_header(authorization)
    try:
        project = session_store.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _ensure_project_access(project, account)
    return project, account


def _require_story_access(
    story_id: str,
    authorization: str | None,
) -> tuple[UserStoryRecord, ProjectConfig, AuthAccount | None]:
    try:
        story = session_store.get_story(story_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    project, account = _require_project_access(story.project_id, authorization)
    return story, project, account


def _require_session_access(
    session_id: str,
    authorization: str | None,
) -> tuple[SessionInfo, IncidentRun, AuthAccount | None]:
    account = _optional_account_from_header(authorization)
    try:
        session = session_store.get_session(session_id)
        run = session_store.get_run(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if run.project is not None:
        _ensure_project_access(run.project, account)
    return session, run, account


def _require_run_access(run_id: str, authorization: str | None) -> tuple[IncidentRun, AuthAccount | None]:
    account = _optional_account_from_header(authorization)
    try:
        run = session_store.get_run_by_id(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if run.project is not None:
        _ensure_project_access(run.project, account)
    return run, account


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "OpenIncident",
        "status": "ok",
    }


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return FileResponse(_dashboard_entrypoint())


@app.get("/dashboard/{full_path:path}")
def dashboard_spa(full_path: str) -> FileResponse:
    return FileResponse(_dashboard_entrypoint())


@app.get("/health")
def health() -> dict[str, object]:
    try:
        storage = session_store.get_storage_health()
        return {
            "status": "ok",
            "storage": storage,
            "frontend_dist_ready": (FRONTEND_DIST_DIR / "index.html").exists(),
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "storage": {"status": "error", "error": str(exc)},
            "frontend_dist_ready": (FRONTEND_DIST_DIR / "index.html").exists(),
        }


@app.get("/system/status")
def system_status() -> dict[str, object]:
    return {
        "api": "ok",
        "storage": session_store.get_storage_health(),
        "database_target": get_database_target(),
        "frontend_dist_ready": (FRONTEND_DIST_DIR / "index.html").exists(),
        "allowed_origins": get_allowed_origins(),
    }


@app.get("/system/agent-training-plan", response_model=AgentTrainingPlan)
def get_agent_training_plan(authorization: str | None = Header(default=None)) -> AgentTrainingPlan:
    _require_account_from_header(authorization)
    return build_agent_training_plan()


@app.get("/system/database/overview", response_model=DatabaseOverview)
def get_database_overview(authorization: str | None = Header(default=None)) -> DatabaseOverview:
    _require_account_from_header(authorization)
    try:
        return DatabaseOverview.model_validate(session_store.get_database_overview())
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/system/database/migrations", response_model=DatabaseMigrationStatus)
def get_database_migrations(authorization: str | None = Header(default=None)) -> DatabaseMigrationStatus:
    _require_account_from_header(authorization)
    try:
        return DatabaseMigrationStatus.model_validate(session_store.get_database_migration_status())
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/system/database/{table_name}", response_model=DatabaseTableRows)
def get_database_table_rows(
    table_name: str,
    limit: int = 50,
    authorization: str | None = Header(default=None),
) -> DatabaseTableRows:
    _require_account_from_header(authorization)
    try:
        rows = session_store.list_database_table_rows(table_name, limit=limit)
        return DatabaseTableRows(
            table_name=table_name,
            limit=limit,
            rows=[DatabaseRowView(table_name=table_name, payload=row) for row in rows],
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/register", response_model=AuthAccount)
def register_account(request: AuthRegisterRequest) -> AuthAccount:
    try:
        return session_store.register_account(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/login", response_model=AuthLoginResponse)
def login_account(request: AuthLoginRequest) -> AuthLoginResponse:
    try:
        return session_store.login_account(request)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/auth/me", response_model=AuthAccount)
def get_authenticated_account(authorization: str | None = Header(default=None)) -> AuthAccount:
    return _require_account_from_header(authorization)


@app.post("/auth/logout")
def logout_account(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = _extract_bearer_token(authorization)
    if authorization is not None and token is None:
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    if token is not None:
        session_store.logout_token(token)
    return {"status": "ok"}


@app.post("/reset", response_model=IncidentObservation)
def reset_environment(request: SessionResetRequest | None = None) -> IncidentObservation:
    global environment
    payload = request or SessionResetRequest()
    try:
        project = payload.project
        if payload.project_id is not None:
            project = session_store.get_project(payload.project_id)
        _, _, environment = session_store.create_session(
            task_id=payload.task_id,
            max_steps=payload.max_steps,
            project=project,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return environment.reset()


@app.post("/projects", response_model=ProjectConfig)
def create_project(request: ProjectCreateRequest, authorization: str | None = Header(default=None)) -> ProjectConfig:
    repository_url = (request.repository_url or "").strip()
    if not repository_url:
        raise HTTPException(status_code=400, detail="Project creation requires a GitHub repository URL")

    metadata = dict(request.metadata)
    if authorization is not None:
        account = _require_account_from_header(authorization)
        metadata.setdefault("owner_id", account.account_id)
        metadata.setdefault("owner_name", account.name)
        metadata.setdefault("owner_email", account.email)
        if account.team:
            metadata.setdefault("owner_team", account.team)

    payload = request.model_copy(
        update={
            "repository_url": repository_url,
            "base_url": (request.base_url or "").strip() or None,
            "metadata": metadata,
        }
    )
    return session_store.create_project(payload)


@app.get("/projects", response_model=list[ProjectConfig])
def list_projects(authorization: str | None = Header(default=None)) -> list[ProjectConfig]:
    account = _optional_account_from_header(authorization)
    projects = session_store.list_projects()
    if account is None:
        return [project for project in projects if not project.metadata.get("owner_id")]
    return [
        project
        for project in projects
        if not project.metadata.get("owner_id") or project.metadata.get("owner_id") == account.account_id
    ]


@app.get("/projects/{project_id}/endpoints", response_model=list[ProjectEndpoint])
def list_project_endpoints(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> list[ProjectEndpoint]:
    _require_project_access(project_id, authorization)
    try:
        return session_store.list_project_endpoints(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/projects/{project_id}/endpoints", response_model=ProjectConfig)
def update_project_endpoints(
    project_id: str,
    request: ProjectEndpointBatchUpdateRequest,
    authorization: str | None = Header(default=None),
) -> ProjectConfig:
    _require_project_access(project_id, authorization)
    try:
        return session_store.set_project_endpoints(project_id, request)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/projects/{project_id}/execution-policy", response_model=SessionExecutionPolicy)
def get_project_execution_policy(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> SessionExecutionPolicy:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_project_execution_policy(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/projects/{project_id}/execution-policy", response_model=SessionExecutionPolicy)
def set_project_execution_policy(
    project_id: str,
    request: SessionExecutionPolicyUpdateRequest,
    authorization: str | None = Header(default=None),
) -> SessionExecutionPolicy:
    _require_project_access(project_id, authorization)
    try:
        return session_store.set_project_execution_policy(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/logs", response_model=list[ProjectLogEntry])
def ingest_project_logs(
    project_id: str,
    request: ProjectLogBatchRequest,
    authorization: str | None = Header(default=None),
) -> list[ProjectLogEntry]:
    _require_project_access(project_id, authorization)
    try:
        return session_store.add_project_logs(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/logs", response_model=list[ProjectLogEntry])
def list_project_logs(project_id: str, authorization: str | None = Header(default=None)) -> list[ProjectLogEntry]:
    _require_project_access(project_id, authorization)
    try:
        return session_store.list_project_logs(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/logs/summary", response_model=ProjectLogSummary)
def get_project_log_summary(project_id: str, authorization: str | None = Header(default=None)) -> ProjectLogSummary:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_project_log_summary(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/projects/{project_id}/logs/connector", response_model=ProjectLogConnectorConfig)
def set_project_log_connector(
    project_id: str,
    request: ProjectLogConnectorRequest,
    authorization: str | None = Header(default=None),
) -> ProjectLogConnectorConfig:
    _require_project_access(project_id, authorization)
    try:
        return session_store.set_project_log_connector(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/logs/connector", response_model=ProjectLogConnectorConfig)
def get_project_log_connector(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectLogConnectorConfig:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_project_log_connector(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/logs/connector/pull", response_model=ProjectLogConnectorPullResult)
def pull_project_logs_from_connector(
    project_id: str,
    request: ProjectLogConnectorPullRequest | None = None,
    authorization: str | None = Header(default=None),
) -> ProjectLogConnectorPullResult:
    _require_project_access(project_id, authorization)
    try:
        return session_store.pull_project_logs_from_connector(project_id, limit=(request.limit if request else 100))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/metrics", response_model=list[ProjectMetricPoint])
def ingest_project_metrics(
    project_id: str,
    request: ProjectMetricBatchRequest,
    authorization: str | None = Header(default=None),
) -> list[ProjectMetricPoint]:
    _require_project_access(project_id, authorization)
    try:
        return session_store.add_project_metrics(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/metrics", response_model=list[ProjectMetricPoint])
def list_project_metrics(project_id: str, authorization: str | None = Header(default=None)) -> list[ProjectMetricPoint]:
    _require_project_access(project_id, authorization)
    try:
        return session_store.list_project_metrics(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/metrics/summary", response_model=ProjectMetricSummary)
def get_project_metric_summary(project_id: str, authorization: str | None = Header(default=None)) -> ProjectMetricSummary:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_project_metric_summary(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/events", response_model=list[ProjectEvent])
def list_project_events(
    project_id: str,
    limit: int = 50,
    authorization: str | None = Header(default=None),
) -> list[ProjectEvent]:
    _require_project_access(project_id, authorization)
    try:
        return session_store.list_project_events(project_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/summary", response_model=ProjectCommandCenterSummary)
def get_project_command_center_summary(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectCommandCenterSummary:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_project_command_center_summary(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/agents", response_model=ProjectAgentRoster)
def get_project_agents(project_id: str, authorization: str | None = Header(default=None)) -> ProjectAgentRoster:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_project_agent_roster(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/agents/coordination", response_model=ProjectAgentCoordinationTrace)
def get_project_agent_coordination(
    project_id: str,
    limit: int = 50,
    authorization: str | None = Header(default=None),
) -> ProjectAgentCoordinationTrace:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_project_agent_coordination_trace(project_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/agents/conversation", response_model=ProjectAgentConversationTrace)
def get_project_agent_conversation(
    project_id: str,
    limit: int = 50,
    authorization: str | None = Header(default=None),
) -> ProjectAgentConversationTrace:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_project_agent_conversation_trace(project_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/projects/{project_id}/testing/environment", response_model=TestEnvironmentConfig)
def set_project_test_environment(
    project_id: str,
    request: TestEnvironmentConfigRequest,
    authorization: str | None = Header(default=None),
) -> TestEnvironmentConfig:
    _require_project_access(project_id, authorization)
    try:
        return session_store.set_test_environment_config(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/testing/environment", response_model=TestEnvironmentConfig)
def get_project_test_environment(project_id: str, authorization: str | None = Header(default=None)) -> TestEnvironmentConfig:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_test_environment_config(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/testing/environment/runs", response_model=list[TestEnvironmentRunResult])
def list_project_test_environment_runs(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> list[TestEnvironmentRunResult]:
    _require_project_access(project_id, authorization)
    try:
        return session_store.list_test_environment_runs(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/testing/environment/run", response_model=TestEnvironmentRunResult)
def run_project_test_environment(
    project_id: str,
    request: TestEnvironmentRunRequest,
    authorization: str | None = Header(default=None),
) -> TestEnvironmentRunResult:
    _require_project_access(project_id, authorization)
    try:
        config = session_store.get_test_environment_config(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not config.enabled:
        raise HTTPException(status_code=400, detail="Testing environment is disabled for this project")
    if not config.repository_url:
        raise HTTPException(status_code=400, detail="Testing environment requires a repository_url")

    try:
        result = run_test_environment(config, request)
    except subprocess.TimeoutExpired as exc:  # type: ignore[name-defined]
        raise HTTPException(status_code=408, detail=f"Testing environment timed out: {exc}") from exc
    except subprocess.CalledProcessError as exc:  # type: ignore[name-defined]
        detail = exc.stderr or exc.stdout or str(exc)
        raise HTTPException(status_code=500, detail=f"Repository preparation failed: {detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not result.success:
        session, run, _ = session_store.create_test_environment_incident(project_id, result)
        result.linked_run_id = run.run_id
        result.linked_session_id = session.session_id

    return session_store.add_test_environment_run(project_id, result)


@app.get("/projects/{project_id}/repo/inspect", response_model=RepoInspectionResult)
def inspect_project_repository(
    project_id: str,
    query: str,
    authorization: str | None = Header(default=None),
) -> RepoInspectionResult:
    project, _ = _require_project_access(project_id, authorization)
    return inspect_repository_for_query(project, query)


@app.get("/projects/{project_id}/frontend/discover", response_model=FrontendSurfaceDiscovery)
def discover_project_frontend(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> FrontendSurfaceDiscovery:
    project, _ = _require_project_access(project_id, authorization)
    workspace_path = session_store.get_latest_test_environment_workspace(project_id)
    return discover_frontend_surface(project, workspace_path=workspace_path)


@app.post("/projects/{project_id}/stories", response_model=list[UserStoryRecord])
def create_project_stories(
    project_id: str,
    request: UserStoryBatchCreateRequest,
    authorization: str | None = Header(default=None),
) -> list[UserStoryRecord]:
    _require_project_access(project_id, authorization)
    try:
        return session_store.create_user_stories(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/stories", response_model=list[UserStoryRecord])
def list_project_stories(project_id: str, authorization: str | None = Header(default=None)) -> list[UserStoryRecord]:
    _require_project_access(project_id, authorization)
    try:
        return session_store.list_project_stories(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/testing/predeploy", response_model=PredeployValidationResult)
def run_predeploy_validation(
    project_id: str,
    rerun_failed_only: bool = False,
    authorization: str | None = Header(default=None),
) -> PredeployValidationResult:
    _require_project_access(project_id, authorization)
    try:
        session_store.get_project(project_id)
        stories = session_store.list_project_stories(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    target_stories = stories
    if rerun_failed_only:
        target_stories = [
            story for story in stories
            if story.status in {StoryStatus.FAILED, StoryStatus.BLOCKED, StoryStatus.PENDING, StoryStatus.ANALYZED}
        ]

    executed_story_ids: list[str] = []
    for story in target_stories:
        if story.analysis is None:
            story = session_store.analyze_story(story.story_id)
        _execute_project_story_internal(story.story_id, authorization)
        executed_story_ids.append(story.story_id)

    if not executed_story_ids:
        executed_story_ids = [story.story_id for story in stories]
    return session_store.complete_predeploy_validation(project_id, executed_story_ids)


@app.post("/stories/{story_id}/analyze", response_model=UserStoryRecord)
def analyze_project_story(story_id: str, authorization: str | None = Header(default=None)) -> UserStoryRecord:
    _require_story_access(story_id, authorization)
    try:
        return session_store.analyze_story(story_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/stories/{story_id}/execute", response_model=UserStoryExecutionResult)
def execute_project_story(story_id: str, authorization: str | None = Header(default=None)) -> UserStoryExecutionResult:
    return _execute_project_story_internal(story_id, authorization)


def _execute_project_story_internal(story_id: str, authorization: str | None) -> UserStoryExecutionResult:
    story, project, _ = _require_story_access(story_id, authorization)
    if story.analysis is None:
        try:
            story = session_store.analyze_story(story_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    primary_domain = story.analysis.primary_domain
    selected_endpoint = None
    if primary_domain in {StoryDomain.FRONTEND, StoryDomain.AUTH} or story.analysis.assigned_agent == AgentRole.FRONTEND_TESTER:
        selected_endpoint = _resolve_project_endpoint(project, preferred_surface="frontend")
        base_url = selected_endpoint.base_url if selected_endpoint else project.base_url
        if not base_url:
            raise HTTPException(status_code=400, detail="Project does not have a frontend base_url configured")
        workspace_path = session_store.get_latest_test_environment_workspace(project.project_id)
        result = execute_frontend_story(story, base_url, project=project, workspace_path=workspace_path)
    elif primary_domain == StoryDomain.API or story.analysis.assigned_agent == AgentRole.API_TESTER:
        selected_endpoint = _resolve_project_endpoint(project, preferred_surface="api")
        base_url = selected_endpoint.base_url if selected_endpoint else project.base_url
        if not base_url:
            raise HTTPException(status_code=400, detail="Project does not have an API base_url configured")
        result = execute_api_story(story, base_url)
    else:
        result = UserStoryExecutionResult(
            story_id=story.story_id,
            project_id=story.project_id,
            status=StoryStatus.BLOCKED,
            summary=(
                "This story was classified into a domain that does not yet have an automated executor. "
                "It is stored and analyzed, but still needs a dedicated connector."
            ),
            evidence=[
                f"Assigned agent: {story.analysis.assigned_agent.value}.",
                f"Primary domain: {story.analysis.primary_domain.value}.",
            ],
        )

    if selected_endpoint is not None and result.output is not None:
        result.output.setdefault("endpoint_id", selected_endpoint.endpoint_id)
        result.output.setdefault("endpoint_label", selected_endpoint.label)
        result.output.setdefault("endpoint_surface", selected_endpoint.surface)
        result.evidence.append(
            f"Target endpoint: {selected_endpoint.label} ({selected_endpoint.surface}) at {selected_endpoint.base_url}."
        )

    if project.repository_url:
        repo_context = inspect_repository_for_story(project, story)
        if repo_context.matches:
            result.evidence.append(
                f"Repository inspection found {len(repo_context.matches)} likely file(s): "
                + ", ".join(match.path for match in repo_context.matches[:3])
            )
            result.output["repo_context"] = repo_context.model_dump(mode="json")
        elif repo_context.error_message:
            result.evidence.append(f"Repository inspection unavailable: {repo_context.error_message}")

    log_summary = session_store.get_project_log_summary(project.project_id)
    if log_summary.total_entries:
        result.evidence.append(
            f"Log summary found {log_summary.error_entries} error entries and {log_summary.warning_entries} warning entries."
        )
        result.output["log_summary"] = log_summary.model_dump(mode="json")
        if log_summary.latest_errors:
            result.evidence.extend(log_summary.latest_errors[:2])

    if result.status == StoryStatus.FAILED:
        snapshot = _story_result_to_snapshot(result, story)
        if snapshot is not None:
            session, run, _ = session_store.create_story_incident(
                project_id=project.project_id,
                story_title=story.title,
                trigger_reason=result.summary,
                signal_snapshot=snapshot,
            )
            result.linked_run_id = run.run_id
            result.linked_session_id = session.session_id
            result.evidence.append(f"Incident {run.run_id[:8]} was opened from this failed story.")

    session_store.attach_story_execution_result(story.story_id, result)
    return result


@app.get("/projects/{project_id}/story-report", response_model=ProjectStoryReport)
def get_project_story_report(project_id: str, authorization: str | None = Header(default=None)) -> ProjectStoryReport:
    _require_project_access(project_id, authorization)
    try:
        return session_store.build_story_report(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/planner-summary", response_model=ProjectPlannerSummary)
def get_project_planner_summary(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectPlannerSummary:
    _require_project_access(project_id, authorization)
    try:
        return session_store.build_planner_summary(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/planner-training-dataset", response_model=ProjectPlannerTrainingDataset)
def get_project_planner_training_dataset(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectPlannerTrainingDataset:
    _require_project_access(project_id, authorization)
    try:
        return session_store.build_planner_training_dataset(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/frontend-training-dataset", response_model=ProjectFrontendTrainingDataset)
def get_project_frontend_training_dataset(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectFrontendTrainingDataset:
    _require_project_access(project_id, authorization)
    try:
        return session_store.build_frontend_training_dataset(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/api-training-dataset", response_model=ProjectApiTrainingDataset)
def get_project_api_training_dataset(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectApiTrainingDataset:
    _require_project_access(project_id, authorization)
    try:
        return session_store.build_api_training_dataset(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/guardian-training-dataset", response_model=ProjectGuardianTrainingDataset)
def get_project_guardian_training_dataset(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectGuardianTrainingDataset:
    _require_project_access(project_id, authorization)
    try:
        return session_store.build_guardian_training_dataset(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/triage-training-dataset", response_model=ProjectTriageTrainingDataset)
def get_project_triage_training_dataset(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectTriageTrainingDataset:
    _require_project_access(project_id, authorization)
    try:
        return session_store.build_triage_training_dataset(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/observability-training-dataset", response_model=ProjectObservabilityTrainingDataset)
def get_project_observability_training_dataset(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectObservabilityTrainingDataset:
    _require_project_access(project_id, authorization)
    try:
        return session_store.build_observability_training_dataset(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/oversight-training-dataset", response_model=ProjectOversightTrainingDataset)
def get_project_oversight_training_dataset(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectOversightTrainingDataset:
    _require_project_access(project_id, authorization)
    try:
        return session_store.build_oversight_training_dataset(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/environment-summary", response_model=ProjectEnvironmentSummary)
def get_project_environment_summary(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectEnvironmentSummary:
    _require_project_access(project_id, authorization)
    try:
        return session_store.build_environment_summary(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/stories/{story_id}/code-context", response_model=RepoInspectionResult)
def get_story_code_context(story_id: str, authorization: str | None = Header(default=None)) -> RepoInspectionResult:
    story, project, _ = _require_story_access(story_id, authorization)
    return inspect_repository_for_story(project, story)


@app.get("/stories/{story_id}/frontend-plan", response_model=FrontendStoryTestPlan)
def get_story_frontend_plan(story_id: str, authorization: str | None = Header(default=None)) -> FrontendStoryTestPlan:
    story, project, _ = _require_story_access(story_id, authorization)
    workspace_path = session_store.get_latest_test_environment_workspace(project.project_id)
    return build_frontend_story_plan(project, story, workspace_path=workspace_path)


@app.put("/projects/{project_id}/monitor", response_model=WebsiteMonitorConfig)
def set_project_monitor(
    project_id: str,
    request: WebsiteMonitorUpdateRequest,
    authorization: str | None = Header(default=None),
) -> WebsiteMonitorConfig:
    _require_project_access(project_id, authorization)
    try:
        return session_store.set_monitor(project_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/monitor", response_model=WebsiteMonitorConfig)
def get_project_monitor(project_id: str, authorization: str | None = Header(default=None)) -> WebsiteMonitorConfig:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_monitor(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/projects/{project_id}/monitor/trigger", response_model=MonitorIncidentTrigger)
def set_project_monitor_trigger(
    project_id: str,
    trigger: MonitorIncidentTrigger,
    authorization: str | None = Header(default=None),
) -> MonitorIncidentTrigger:
    _require_project_access(project_id, authorization)
    try:
        return session_store.set_monitor_trigger(project_id, trigger)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/monitor/trigger", response_model=MonitorIncidentTrigger)
def get_project_monitor_trigger(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> MonitorIncidentTrigger:
    _require_project_access(project_id, authorization)
    return session_store.get_monitor_trigger(project_id)


@app.get("/projects/{project_id}/health", response_model=WebsiteHealthSnapshot)
def get_project_health(project_id: str, authorization: str | None = Header(default=None)) -> WebsiteHealthSnapshot:
    _require_project_access(project_id, authorization)
    try:
        return session_store.get_health_snapshot(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/monitor/check", response_model=WebsiteHealthSnapshot)
def run_project_monitor_check(project_id: str, authorization: str | None = Header(default=None)) -> WebsiteHealthSnapshot:
    project, _ = _require_project_access(project_id, authorization)
    try:
        monitor = session_store.get_monitor(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    endpoint = _resolve_project_endpoint(project, endpoint_id=monitor.endpoint_id) if monitor.endpoint_id else None
    target_base_url = (endpoint.base_url if endpoint else monitor.base_url).rstrip("/")
    healthcheck_path = monitor.healthcheck_path or (endpoint.healthcheck_path if endpoint else project.healthcheck_path)
    target_url = f"{target_base_url}{healthcheck_path}"
    if not monitor.enabled:
        snapshot = WebsiteHealthSnapshot(
            project_id=project_id,
            endpoint_id=endpoint.endpoint_id if endpoint else monitor.endpoint_id,
            endpoint_label=endpoint.label if endpoint else None,
            endpoint_surface=endpoint.surface if endpoint else None,
            status="disabled",
            target_url=target_url,
            error_message="Website monitor is disabled for this project.",
        )
        return session_store.set_health_snapshot(snapshot)

    started_at = perf_counter()
    try:
        response = requests.get(
            target_url,
            headers=monitor.headers,
            timeout=monitor.timeout_seconds,
        )
        response_time_ms = round((perf_counter() - started_at) * 1000, 2)
        is_healthy = response.status_code == monitor.expected_status
        snapshot = WebsiteHealthSnapshot(
            project_id=project_id,
            endpoint_id=endpoint.endpoint_id if endpoint else monitor.endpoint_id,
            endpoint_label=endpoint.label if endpoint else None,
            endpoint_surface=endpoint.surface if endpoint else None,
            status="healthy" if is_healthy else "unhealthy",
            target_url=target_url,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            error_message=None if is_healthy else f"Expected {monitor.expected_status}, got {response.status_code}",
            response_excerpt=response.text[:300] if response.text else None,
        )
    except requests.RequestException as exc:
        response_time_ms = round((perf_counter() - started_at) * 1000, 2)
        snapshot = WebsiteHealthSnapshot(
            project_id=project_id,
            endpoint_id=endpoint.endpoint_id if endpoint else monitor.endpoint_id,
            endpoint_label=endpoint.label if endpoint else None,
            endpoint_surface=endpoint.surface if endpoint else None,
            status="unreachable",
            target_url=target_url,
            response_time_ms=response_time_ms,
            error_message=str(exc),
        )

    snapshot = session_store.set_health_snapshot(snapshot)
    trigger = session_store.get_monitor_trigger(project_id)
    if snapshot.status == "healthy":
        session_store.resolve_recovered_runs(project_id, snapshot)
    elif trigger.enabled and trigger.auto_create_run and snapshot.status in {"unhealthy", "unreachable"}:
        reason = snapshot.error_message or f"Health check reported status {snapshot.status}"
        session_store.create_monitor_incident(
            project_id=project_id,
            trigger_reason=reason,
            signal_snapshot=snapshot,
        )
    return snapshot


@app.post("/projects/{project_id}/checks/api", response_model=ProjectValidationSnapshot)
def run_project_api_check(
    project_id: str,
    request: ProjectApiCheckRequest,
    authorization: str | None = Header(default=None),
) -> ProjectValidationSnapshot:
    project, _ = _require_project_access(project_id, authorization)

    endpoint = _resolve_project_endpoint(
        project,
        endpoint_id=request.endpoint_id,
        preferred_surface="api",
    )
    base_url = endpoint.base_url if endpoint else project.base_url
    if not base_url:
        raise HTTPException(status_code=400, detail="Project does not have an API base_url configured")

    path = request.path if request.path.startswith("/") else f"/{request.path}"
    target_url = f"{base_url.rstrip('/')}{path}"
    started_at = perf_counter()
    try:
        response = requests.request(
            request.method.upper(),
            target_url,
            headers=request.headers,
            json=request.body,
            timeout=request.timeout_seconds,
        )
        response_time_ms = round((perf_counter() - started_at) * 1000, 2)
        is_healthy = response.status_code == request.expected_status
        snapshot = ProjectValidationSnapshot(
            project_id=project_id,
            endpoint_id=endpoint.endpoint_id if endpoint else None,
            endpoint_label=endpoint.label if endpoint else None,
            endpoint_surface=endpoint.surface if endpoint else None,
            check_type="api",
            label=request.label or f"API {request.method.upper()} {path}",
            target_url=target_url,
            status="healthy" if is_healthy else "unhealthy",
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            error_message=None if is_healthy else f"Expected {request.expected_status}, got {response.status_code}",
            response_excerpt=response.text[:300] if response.text else None,
        )
    except requests.RequestException as exc:
        response_time_ms = round((perf_counter() - started_at) * 1000, 2)
        snapshot = ProjectValidationSnapshot(
            project_id=project_id,
            endpoint_id=endpoint.endpoint_id if endpoint else None,
            endpoint_label=endpoint.label if endpoint else None,
            endpoint_surface=endpoint.surface if endpoint else None,
            check_type="api",
            label=request.label or f"API {request.method.upper()} {path}",
            target_url=target_url,
            status="unreachable",
            response_time_ms=response_time_ms,
            error_message=str(exc),
        )

    snapshot = session_store.add_validation_snapshot(snapshot)
    trigger = session_store.get_monitor_trigger(project_id)
    if snapshot.status == "healthy":
        session_store.resolve_recovered_runs(project_id, snapshot)
    elif trigger.enabled and trigger.auto_create_run and snapshot.status in {"unhealthy", "unreachable"}:
        reason = snapshot.error_message or f"{snapshot.label} reported status {snapshot.status}"
        session_store.create_monitor_incident(
            project_id=project_id,
            trigger_reason=reason,
            signal_snapshot=snapshot,
        )
    return snapshot


@app.post("/projects/{project_id}/checks/browser", response_model=ProjectValidationSnapshot)
def run_project_browser_check(
    project_id: str,
    request: ProjectBrowserCheckRequest,
    authorization: str | None = Header(default=None),
) -> ProjectValidationSnapshot:
    project, _ = _require_project_access(project_id, authorization)

    endpoint = _resolve_project_endpoint(
        project,
        endpoint_id=request.endpoint_id,
        preferred_surface="frontend",
    )
    base_url = endpoint.base_url if endpoint else project.base_url
    if not base_url:
        raise HTTPException(status_code=400, detail="Project does not have a frontend base_url configured")

    path = request.path if request.path.startswith("/") else f"/{request.path}"
    target_url = f"{base_url.rstrip('/')}{path}"
    try:
        browser_mode = request.browser_mode.lower()
        if browser_mode == "playwright":
            result = run_playwright_browser_check(target_url, request)
        else:
            result = run_http_browser_check(target_url, request)
        snapshot = ProjectValidationSnapshot(
            project_id=project_id,
            endpoint_id=endpoint.endpoint_id if endpoint else None,
            endpoint_label=endpoint.label if endpoint else None,
            endpoint_surface=endpoint.surface if endpoint else None,
            check_type="browser",
            label=request.label or f"Browser {path}",
            target_url=target_url,
            status=result["status"],
            status_code=result["status_code"],
            response_time_ms=result["response_time_ms"],
            error_message=result["error_message"],
            response_excerpt=result["response_excerpt"],
            engine=result["engine"],
            observed_url=result["observed_url"],
            page_title=result["page_title"],
        )
    except requests.RequestException as exc:
        snapshot = ProjectValidationSnapshot(
            project_id=project_id,
            endpoint_id=endpoint.endpoint_id if endpoint else None,
            endpoint_label=endpoint.label if endpoint else None,
            endpoint_surface=endpoint.surface if endpoint else None,
            check_type="browser",
            label=request.label or f"Browser {path}",
            target_url=target_url,
            status="unreachable",
            error_message=str(exc),
            engine=request.browser_mode.lower(),
            observed_url=target_url,
        )

    snapshot = session_store.add_validation_snapshot(snapshot)
    trigger = session_store.get_monitor_trigger(project_id)
    if snapshot.status == "healthy":
        session_store.resolve_recovered_runs(project_id, snapshot)
    elif trigger.enabled and trigger.auto_create_run and snapshot.status in {"unhealthy", "unreachable"}:
        reason = snapshot.error_message or f"{snapshot.label} reported status {snapshot.status}"
        session_store.create_monitor_incident(
            project_id=project_id,
            trigger_reason=reason,
            signal_snapshot=snapshot,
        )
    return snapshot


@app.get("/projects/{project_id}/checks", response_model=list[ProjectValidationSnapshot])
def list_project_checks(project_id: str, authorization: str | None = Header(default=None)) -> list[ProjectValidationSnapshot]:
    _require_project_access(project_id, authorization)
    return session_store.list_validation_snapshots(project_id)


@app.post("/projects/{project_id}/diagnostics/sweep", response_model=ProjectDiagnosticSweepResult)
def run_project_diagnostics_sweep(
    project_id: str,
    authorization: str | None = Header(default=None),
) -> ProjectDiagnosticSweepResult:
    project, _ = _require_project_access(project_id, authorization)
    started_at = datetime.now(timezone.utc)
    issues: list[ProjectDiagnosticIssue] = []
    health_snapshot: WebsiteHealthSnapshot | None = None
    browser_snapshot: ProjectValidationSnapshot | None = None
    api_snapshot: ProjectValidationSnapshot | None = None

    try:
        health_snapshot = run_project_monitor_check(project_id, authorization)
    except HTTPException as exc:
        _log_issue(
            issues,
            severity="warning",
            category="health",
            title="Health check skipped",
            detail=str(exc.detail),
        )
    except Exception as exc:
        _log_issue(
            issues,
            severity="error",
            category="health",
            title="Health check failed",
            detail=str(exc),
        )

    frontend_endpoint = None
    try:
        frontend_endpoint = _resolve_project_endpoint(project, preferred_surface="frontend")
    except HTTPException:
        frontend_endpoint = None

    if frontend_endpoint is not None or project.base_url:
        browser_request = ProjectBrowserCheckRequest(
            endpoint_id=frontend_endpoint.endpoint_id if frontend_endpoint else None,
            path="/",
            expected_text=None,
            expected_selector=None,
            timeout_seconds=15,
            label="Diagnostic browser smoke",
            browser_mode="playwright",
            wait_until="networkidle",
        )
        try:
            browser_snapshot = run_project_browser_check(project_id, browser_request, authorization)
        except Exception as exc:
            _log_issue(
                issues,
                severity="warning",
                category="browser",
                title="Playwright browser check failed; retrying HTTP mode",
                detail=str(exc),
            )
            fallback_request = browser_request.model_copy(update={"browser_mode": "http"})
            try:
                browser_snapshot = run_project_browser_check(project_id, fallback_request, authorization)
            except Exception as fallback_exc:
                _log_issue(
                    issues,
                    severity="error",
                    category="browser",
                    title="Browser validation failed",
                    detail=str(fallback_exc),
                )
    else:
        _log_issue(
            issues,
            severity="warning",
            category="browser",
            title="Browser check skipped",
            detail="No frontend endpoint is configured for this project.",
        )

    api_endpoint = None
    try:
        api_endpoint = _resolve_project_endpoint(project, preferred_surface="api")
    except HTTPException:
        api_endpoint = None

    if api_endpoint is not None or project.base_url:
        api_request = ProjectApiCheckRequest(
            endpoint_id=api_endpoint.endpoint_id if api_endpoint else None,
            method="GET",
            path=(api_endpoint.healthcheck_path if api_endpoint else project.healthcheck_path) or "/health",
            expected_status=200,
            timeout_seconds=30,
            headers={},
            body=None,
            label="Diagnostic API smoke",
        )
        try:
            api_snapshot = run_project_api_check(project_id, api_request, authorization)
        except Exception as exc:
            _log_issue(
                issues,
                severity="error",
                category="api",
                title="API validation failed",
                detail=str(exc),
            )
    else:
        _log_issue(
            issues,
            severity="warning",
            category="api",
            title="API check skipped",
            detail="No backend/API endpoint is configured for this project.",
        )

    try:
        log_summary = session_store.get_project_log_summary(project_id)
    except Exception as exc:
        log_summary = None
        _log_issue(
            issues,
            severity="warning",
            category="logs",
            title="Log summary failed",
            detail=str(exc),
        )
    log_findings, log_issues = _build_log_findings(log_summary)
    issues.extend(log_issues)

    open_runs = [run for run in session_store.list_runs(project_id=project_id) if run.status != "resolved"]
    triaged_run_ids: list[str] = []
    for run in open_runs:
        try:
            triage_result = build_run_triage(session_store, run.session_id)
            refreshed_run = session_store.get_run(run.session_id)
            session_store.record_triage_summary(project_id, refreshed_run, triage_result)
            session_store.record_triage_activity(project_id, triage_result.confidence, triage_result.summary)
            triaged_run_ids.append(run.run_id)
        except Exception as exc:
            _log_issue(
                issues,
                severity="warning",
                category="triage",
                title=f"Triage failed for run {run.run_id[:8]}",
                detail=str(exc),
            )

    first_open_run = open_runs[0] if open_runs else None
    handoffs_recorded = session_store.record_diagnostic_sweep_activity(
        project_id,
        health_status=health_snapshot.status if health_snapshot else None,
        browser_status=browser_snapshot.status if browser_snapshot else None,
        api_status=api_snapshot.status if api_snapshot else None,
        log_summary=log_summary,
        open_incident_count=len(open_runs),
        triaged_run_count=len(triaged_run_ids),
        related_run_id=first_open_run.run_id if first_open_run else None,
        related_session_id=first_open_run.session_id if first_open_run else None,
    )

    healthy_signals = sum(
        1
        for status in (
            health_snapshot.status if health_snapshot else None,
            browser_snapshot.status if browser_snapshot else None,
            api_snapshot.status if api_snapshot else None,
        )
        if status == "healthy"
    )
    severity_counts = {
        "error": sum(issue.severity == "error" for issue in issues),
        "warning": sum(issue.severity == "warning" for issue in issues),
    }
    summary = (
        f"Diagnostics sweep complete: healthy_signals={healthy_signals}/3, "
        f"open_incidents={len(open_runs)}, triaged_runs={len(triaged_run_ids)}, "
        f"log_errors={(log_summary.error_entries if log_summary else 0)}, "
        f"warnings={severity_counts['warning']}, errors={severity_counts['error']}."
    )

    completed_at = datetime.now(timezone.utc)
    return ProjectDiagnosticSweepResult(
        project_id=project_id,
        started_at=started_at,
        completed_at=completed_at,
        health_snapshot=health_snapshot,
        browser_snapshot=browser_snapshot,
        api_snapshot=api_snapshot,
        log_summary=log_summary,
        log_findings=log_findings,
        open_incident_ids=[run.run_id for run in open_runs],
        triaged_run_ids=triaged_run_ids,
        agent_handoffs_recorded=handoffs_recorded,
        issues=issues,
        summary=summary,
    )


@app.get("/runs", response_model=list[IncidentRun])
def list_runs(
    project_id: str | None = None,
    authorization: str | None = Header(default=None),
) -> list[IncidentRun]:
    if project_id is not None:
        _require_project_access(project_id, authorization)
        return session_store.list_runs(project_id=project_id)

    account = _optional_account_from_header(authorization)
    runs = session_store.list_runs()
    if account is None:
        return [
            run
            for run in runs
            if run.project is None or not run.project.metadata.get("owner_id")
        ]
    return [
        run
        for run in runs
        if run.project is None
        or not run.project.metadata.get("owner_id")
        or run.project.metadata.get("owner_id") == account.account_id
    ]


@app.post("/sessions/reset", response_model=SessionResetResponse)
def create_session(
    request: SessionResetRequest | None = None,
    authorization: str | None = Header(default=None),
) -> SessionResetResponse:
    payload = request or SessionResetRequest()
    try:
        project = payload.project
        if payload.project_id is not None:
            project, _ = _require_project_access(payload.project_id, authorization)
        elif project is not None:
            _ensure_project_access(project, _optional_account_from_header(authorization))
        session, run, session_environment = session_store.create_session(
            task_id=payload.task_id,
            max_steps=payload.max_steps,
            project=project,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    observation = session_environment.reset()
    run = session_store.record_step(session.session_id, reward=0.0, observation=observation, done=False)
    return SessionResetResponse(session=session, run=run, observation=observation)


@app.get("/sessions/{session_id}/execution-policy", response_model=SessionExecutionPolicy)
def get_session_execution_policy(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> SessionExecutionPolicy:
    _require_session_access(session_id, authorization)
    try:
        return session_store.get_session_execution_policy(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/sessions/{session_id}/execution-policy", response_model=SessionExecutionPolicy)
def set_session_execution_policy(
    session_id: str,
    request: SessionExecutionPolicyUpdateRequest,
    authorization: str | None = Header(default=None),
) -> SessionExecutionPolicy:
    _require_session_access(session_id, authorization)
    try:
        return session_store.set_session_execution_policy(session_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/step", response_model=StepResult)
def step_environment(action: IncidentAction) -> StepResult:
    observation, reward, done, info = environment.step(action)
    return StepResult(observation=observation, reward=reward, done=done, info=info)


@app.post("/sessions/step", response_model=SessionStepResult)
def step_session(request: SessionStepRequest, authorization: str | None = Header(default=None)) -> SessionStepResult:
    _require_session_access(request.session_id, authorization)
    try:
        session_environment = session_store.get_environment(request.session_id)
        can_execute, block_reason, policy = session_store.evaluate_session_action(
            request.session_id,
            request.action,
            approval_token=request.approval_token,
        )
        if can_execute:
            observation, reward, done, info = session_environment.step(request.action)
            info["policy_mode"] = policy.mode.value
        else:
            current_observation = session_environment.state()
            observation = current_observation.model_copy(
                update={
                    "last_action": request.action.action_type.value,
                    "last_action_error": block_reason,
                }
            )
            reward = policy.blocked_reward
            done = False
            info = {
                "blocked": True,
                "policy_mode": policy.mode.value,
                "blocked_reason": block_reason,
            }
        session = session_store.touch(request.session_id)
        run = session_store.record_step(request.session_id, reward=reward, observation=observation, done=done)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionStepResult(
        session=session,
        run=run,
        observation=observation,
        reward=reward,
        done=done,
        info=info,
    )


@app.get("/state", response_model=IncidentObservation)
def get_state() -> IncidentObservation:
    return environment.state()


@app.get("/sessions/{session_id}/state", response_model=IncidentObservation)
def get_session_state(session_id: str, authorization: str | None = Header(default=None)) -> IncidentObservation:
    _require_session_access(session_id, authorization)
    try:
        session_store.touch(session_id)
        return session_store.get_environment(session_id).state()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/sessions/{session_id}", response_model=SessionInfo)
def get_session(session_id: str, authorization: str | None = Header(default=None)) -> SessionInfo:
    _require_session_access(session_id, authorization)
    try:
        return session_store.touch(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/sessions/{session_id}/run", response_model=IncidentRun)
def get_session_run(session_id: str, authorization: str | None = Header(default=None)) -> IncidentRun:
    _require_session_access(session_id, authorization)
    try:
        session_store.touch(session_id)
        return session_store.get_run(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/sessions/{session_id}/triage", response_model=RunTriageSummary)
def triage_session(session_id: str, authorization: str | None = Header(default=None)) -> RunTriageSummary:
    _require_session_access(session_id, authorization)
    try:
        session_store.touch(session_id)
        result = build_run_triage(session_store, session_id)
        session = session_store.get_session(session_id)
        if session.project:
            run = session_store.get_run(session_id)
            session_store.record_triage_summary(session.project.project_id, run, result)
            session_store.record_triage_activity(session.project.project_id, result.confidence, result.summary)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/runs/{run_id}/triage", response_model=RunTriageSummary)
def triage_run(run_id: str, authorization: str | None = Header(default=None)) -> RunTriageSummary:
    _require_run_access(run_id, authorization)
    try:
        run = session_store.get_run_by_id(run_id)
        session_store.touch(run.session_id)
        result = build_run_triage(session_store, run.session_id)
        if run.project:
            refreshed_run = session_store.get_run(run.session_id)
            session_store.record_triage_summary(run.project.project_id, refreshed_run, result)
            session_store.record_triage_activity(run.project.project_id, result.confidence, result.summary)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def main() -> None:
    import uvicorn

    uvicorn.run("server.app:app", host="0.0.0.0", port=get_api_port())


if __name__ == "__main__":
    main()
