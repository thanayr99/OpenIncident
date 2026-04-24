from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
from uuid import uuid4

from models import (
    AuthAccount,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthRegisterRequest,
    StoredAuthAccount,
    AgentCoordinationEntry,
    AgentConversationMessage,
    AgentMaturity,
    AgentProfile,
    AgentRole,
    IncidentRun,
    PredeployValidationResult,
    GuardianDecisionRecord,
    ProjectAgentRoster,
    ProjectAgentCoordinationTrace,
    ProjectAgentConversationTrace,
    ProjectCommandCenterSummary,
    ProjectConfig,
    ProjectEnvironmentSummary,
    ProjectEvent,
    ProjectGuardianTrainingDataset,
    ProjectLogBatchRequest,
    ProjectLogConnectorConfig,
    ProjectLogConnectorPullResult,
    ProjectLogConnectorRequest,
    ProjectLogEntry,
    ProjectLogSummary,
    ProjectMetricBatchRequest,
    ProjectMetricPoint,
    ProjectMetricSeries,
    ProjectMetricSummary,
    ProjectObservabilityTrainingDataset,
    ProjectOversightTrainingDataset,
    ProjectStoryReport,
    RunTriageSummary,
    ProjectTriageTrainingDataset,
    TestEnvironmentConfig,
    TestEnvironmentConfigRequest,
    TestEnvironmentRunResult,
    ProjectCreateRequest,
    ProjectValidationSnapshot,
    ProjectEndpoint,
    ProjectEndpointInput,
    ProjectEndpointBatchUpdateRequest,
    SessionInfo,
    StoryStatus,
    UserStoryAnalysis,
    UserStoryBatchCreateRequest,
    UserStoryExecutionResult,
    UserStoryInput,
    UserStoryRecord,
    TriageTrainingRecord,
    ObservabilityTrainingRecord,
    WebsiteHealthSnapshot,
    MonitorIncidentTrigger,
    OversightAuditRecord,
    WebsiteMonitorConfig,
    WebsiteMonitorUpdateRequest,
)
from server.environment import ProductionIncidentEnv
from server.config import get_database_url
from server.log_engine import create_log_entries, pull_logs_from_connector, summarize_logs
from server.state_backend import build_state_backend
from server.story_engine import (
    analyze_story,
    build_api_training_dataset,
    build_frontend_training_dataset,
    build_planner_summary,
    build_planner_training_dataset,
    build_story_report,
)
from server.test_environment import inspect_workspace


class InMemorySessionStore:
    _AGENT_BLUEPRINTS = {
        AgentRole.PLANNER: ("Planner Agent", "Classifies and routes user stories into reliable execution paths."),
        AgentRole.FRONTEND_TESTER: ("Frontend Test Agent", "Runs browser and UI validation against rendered journeys."),
        AgentRole.API_TESTER: ("API Test Agent", "Validates backend endpoints and response contracts."),
        AgentRole.DATABASE_ANALYST: ("Database Agent", "Reasons about persistence, records, and backend data changes."),
        AgentRole.RELIABILITY_ANALYST: ("Reliability Agent", "Correlates logs, metrics, and incidents for diagnosis."),
        AgentRole.TEST_ENV_GUARDIAN: ("Test Environment Guardian", "Blocks risky releases until story validation is complete."),
        AgentRole.OVERSIGHT: ("Oversight Agent", "Audits agent decisions and checks closure quality."),
    }

    def __init__(self, store_path: str | Path | None = None) -> None:
        self._store_path = Path(store_path or "data/openincident_store.json")
        self._state_backend = build_state_backend(
            store_path=store_path,
            database_url=get_database_url(),
        )
        self._auth_accounts: dict[str, StoredAuthAccount] = {}
        self._auth_tokens: dict[str, str] = {}
        self._auth_email_index: dict[str, str] = {}
        self._projects: dict[str, ProjectConfig] = {}
        self._monitors: dict[str, WebsiteMonitorConfig] = {}
        self._monitor_triggers: dict[str, MonitorIncidentTrigger] = {}
        self._health_snapshots: dict[str, WebsiteHealthSnapshot] = {}
        self._validation_snapshots: dict[str, list[ProjectValidationSnapshot]] = {}
        self._project_logs: dict[str, list[ProjectLogEntry]] = {}
        self._log_connectors: dict[str, ProjectLogConnectorConfig] = {}
        self._project_metrics: dict[str, list[ProjectMetricPoint]] = {}
        self._project_events: dict[str, list[ProjectEvent]] = {}
        self._project_agents: dict[str, list[AgentProfile]] = {}
        self._agent_coordination: dict[str, list[AgentCoordinationEntry]] = {}
        self._agent_conversations: dict[str, list[AgentConversationMessage]] = {}
        self._test_env_configs: dict[str, TestEnvironmentConfig] = {}
        self._test_env_runs: dict[str, list[TestEnvironmentRunResult]] = {}
        self._guardian_decisions: dict[str, list[GuardianDecisionRecord]] = {}
        self._triage_records: dict[str, list[TriageTrainingRecord]] = {}
        self._observability_records: dict[str, list[ObservabilityTrainingRecord]] = {}
        self._sessions: dict[str, SessionInfo] = {}
        self._environments: dict[str, ProductionIncidentEnv] = {}
        self._runs: dict[str, IncidentRun] = {}
        self._stories: dict[str, UserStoryRecord] = {}
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _build_default_agents(self, project_id: str) -> list[AgentProfile]:
        return [
            AgentProfile(
                agent_id=uuid4().hex,
                project_id=project_id,
                role=role,
                display_name=display_name,
                specialization=specialization,
                maturity=AgentMaturity.BOOTSTRAP,
                trust_score=0.5,
            )
            for role, (display_name, specialization) in self._AGENT_BLUEPRINTS.items()
        ]

    def _recompute_agent_maturity(self, agent: AgentProfile) -> None:
        total = agent.completed_tasks + agent.failed_tasks
        success_rate = agent.completed_tasks / total if total else 0.0
        if total >= 16 and success_rate >= 0.88:
            agent.maturity = AgentMaturity.LEAD
        elif total >= 10 and success_rate >= 0.8:
            agent.maturity = AgentMaturity.SPECIALIST
        elif total >= 5 and success_rate >= 0.65:
            agent.maturity = AgentMaturity.OPERATIONAL
        elif total >= 2:
            agent.maturity = AgentMaturity.LEARNING
        else:
            agent.maturity = AgentMaturity.BOOTSTRAP

    def _agent_note(self, agent: AgentProfile, note: str) -> None:
        if note not in agent.notes:
            agent.notes.insert(0, note)
        agent.notes = agent.notes[:8]

    def _update_agent_activity(
        self,
        project_id: str,
        role: AgentRole,
        *,
        success: bool | None = None,
        note: str | None = None,
        story_validated: bool = False,
        incident_triaged: bool = False,
    ) -> AgentProfile:
        agents = self._project_agents.setdefault(project_id, self._build_default_agents(project_id))
        agent = next((item for item in agents if item.role == role), None)
        if agent is None:
            display_name, specialization = self._AGENT_BLUEPRINTS[role]
            agent = AgentProfile(
                agent_id=uuid4().hex,
                project_id=project_id,
                role=role,
                display_name=display_name,
                specialization=specialization,
            )
            agents.append(agent)

        if success is True:
            agent.completed_tasks += 1
            agent.trust_score = min(0.98, round(agent.trust_score + 0.04, 2))
        elif success is False:
            agent.failed_tasks += 1
            agent.trust_score = max(0.15, round(agent.trust_score - 0.05, 2))

        if story_validated:
            agent.stories_validated += 1
        if incident_triaged:
            agent.incidents_triaged += 1
        if note:
            self._agent_note(agent, note)

        agent.last_active_at = datetime.now(timezone.utc)
        self._recompute_agent_maturity(agent)
        self._project_agents[project_id] = agents
        return agent

    def _load(self) -> None:
        if hasattr(self._state_backend, "load_application_state"):
            raw_payload = self._state_backend.load_application_state()
        else:
            raw_payload = self._state_backend.load_state()
        if not raw_payload:
            return
        self._auth_accounts = {
            account_id: StoredAuthAccount.model_validate(account_payload)
            for account_id, account_payload in raw_payload.get("auth_accounts", {}).items()
        }
        self._auth_tokens = {
            token: account_id
            for token, account_id in raw_payload.get("auth_tokens", {}).items()
            if account_id in self._auth_accounts
        }
        self._auth_email_index = {
            account.email.strip().lower(): account_id
            for account_id, account in self._auth_accounts.items()
        }
        self._projects = {
            project_id: self._ensure_project_endpoint_defaults(ProjectConfig.model_validate(project_payload))
            for project_id, project_payload in raw_payload.get("projects", {}).items()
        }
        self._monitors = {
            project_id: WebsiteMonitorConfig.model_validate(monitor_payload)
            for project_id, monitor_payload in raw_payload.get("monitors", {}).items()
        }
        self._monitor_triggers = {
            project_id: MonitorIncidentTrigger.model_validate(trigger_payload)
            for project_id, trigger_payload in raw_payload.get("monitor_triggers", {}).items()
        }
        self._health_snapshots = {
            project_id: WebsiteHealthSnapshot.model_validate(snapshot_payload)
            for project_id, snapshot_payload in raw_payload.get("health_snapshots", {}).items()
        }
        self._validation_snapshots = {
            project_id: [
                ProjectValidationSnapshot.model_validate(snapshot_payload)
                for snapshot_payload in snapshots
            ]
            for project_id, snapshots in raw_payload.get("validation_snapshots", {}).items()
        }
        self._project_logs = {
            project_id: [ProjectLogEntry.model_validate(entry_payload) for entry_payload in entries]
            for project_id, entries in raw_payload.get("project_logs", {}).items()
        }
        self._log_connectors = {
            project_id: ProjectLogConnectorConfig.model_validate(payload)
            for project_id, payload in raw_payload.get("log_connectors", {}).items()
        }
        self._project_metrics = {
            project_id: [ProjectMetricPoint.model_validate(entry_payload) for entry_payload in entries]
            for project_id, entries in raw_payload.get("project_metrics", {}).items()
        }
        self._project_events = {
            project_id: [ProjectEvent.model_validate(entry_payload) for entry_payload in entries]
            for project_id, entries in raw_payload.get("project_events", {}).items()
        }
        self._project_agents = {
            project_id: [AgentProfile.model_validate(entry_payload) for entry_payload in entries]
            for project_id, entries in raw_payload.get("project_agents", {}).items()
        }
        self._agent_coordination = {
            project_id: [AgentCoordinationEntry.model_validate(entry_payload) for entry_payload in entries]
            for project_id, entries in raw_payload.get("agent_coordination", {}).items()
        }
        self._agent_conversations = {
            project_id: [AgentConversationMessage.model_validate(entry_payload) for entry_payload in entries]
            for project_id, entries in raw_payload.get("agent_conversations", {}).items()
        }
        self._test_env_configs = {
            project_id: TestEnvironmentConfig.model_validate(payload)
            for project_id, payload in raw_payload.get("test_env_configs", {}).items()
        }
        self._test_env_runs = {
            project_id: [TestEnvironmentRunResult.model_validate(payload) for payload in entries]
            for project_id, entries in raw_payload.get("test_env_runs", {}).items()
        }
        self._guardian_decisions = {
            project_id: [GuardianDecisionRecord.model_validate(payload) for payload in entries]
            for project_id, entries in raw_payload.get("guardian_decisions", {}).items()
        }
        self._triage_records = {
            project_id: [TriageTrainingRecord.model_validate(payload) for payload in entries]
            for project_id, entries in raw_payload.get("triage_records", {}).items()
        }
        self._observability_records = {
            project_id: [ObservabilityTrainingRecord.model_validate(payload) for payload in entries]
            for project_id, entries in raw_payload.get("observability_records", {}).items()
        }
        self._sessions = {
            session_id: SessionInfo.model_validate(session_payload)
            for session_id, session_payload in raw_payload.get("sessions", {}).items()
        }
        self._runs = {
            session_id: IncidentRun.model_validate(run_payload)
            for session_id, run_payload in raw_payload.get("runs", {}).items()
        }
        self._stories = {
            story_id: UserStoryRecord.model_validate(story_payload)
            for story_id, story_payload in raw_payload.get("stories", {}).items()
        }
        self._environments = {
            session_id: ProductionIncidentEnv.from_snapshot(snapshot)
            for session_id, snapshot in raw_payload.get("environments", {}).items()
        }
        self._state_backend.save_state(raw_payload)

    def _save(self) -> None:
        payload = {
            "auth_accounts": {
                account_id: account.model_dump(mode="json")
                for account_id, account in self._auth_accounts.items()
            },
            "auth_tokens": {
                token: account_id
                for token, account_id in self._auth_tokens.items()
                if account_id in self._auth_accounts
            },
            "projects": {
                project_id: project.model_dump(mode="json")
                for project_id, project in self._projects.items()
            },
            "monitors": {
                project_id: monitor.model_dump(mode="json")
                for project_id, monitor in self._monitors.items()
            },
            "monitor_triggers": {
                project_id: trigger.model_dump(mode="json")
                for project_id, trigger in self._monitor_triggers.items()
            },
            "health_snapshots": {
                project_id: snapshot.model_dump(mode="json")
                for project_id, snapshot in self._health_snapshots.items()
            },
            "validation_snapshots": {
                project_id: [snapshot.model_dump(mode="json") for snapshot in snapshots]
                for project_id, snapshots in self._validation_snapshots.items()
            },
            "project_logs": {
                project_id: [entry.model_dump(mode="json") for entry in entries]
                for project_id, entries in self._project_logs.items()
            },
            "log_connectors": {
                project_id: config.model_dump(mode="json")
                for project_id, config in self._log_connectors.items()
            },
            "project_metrics": {
                project_id: [entry.model_dump(mode="json") for entry in entries]
                for project_id, entries in self._project_metrics.items()
            },
            "project_events": {
                project_id: [entry.model_dump(mode="json") for entry in entries]
                for project_id, entries in self._project_events.items()
            },
            "project_agents": {
                project_id: [entry.model_dump(mode="json") for entry in entries]
                for project_id, entries in self._project_agents.items()
            },
            "agent_coordination": {
                project_id: [entry.model_dump(mode="json") for entry in entries]
                for project_id, entries in self._agent_coordination.items()
            },
            "agent_conversations": {
                project_id: [entry.model_dump(mode="json") for entry in entries]
                for project_id, entries in self._agent_conversations.items()
            },
            "test_env_configs": {
                project_id: config.model_dump(mode="json")
                for project_id, config in self._test_env_configs.items()
            },
            "test_env_runs": {
                project_id: [entry.model_dump(mode="json") for entry in entries]
                for project_id, entries in self._test_env_runs.items()
            },
            "guardian_decisions": {
                project_id: [entry.model_dump(mode="json") for entry in entries]
                for project_id, entries in self._guardian_decisions.items()
            },
            "triage_records": {
                project_id: [entry.model_dump(mode="json") for entry in entries]
                for project_id, entries in self._triage_records.items()
            },
            "observability_records": {
                project_id: [entry.model_dump(mode="json") for entry in entries]
                for project_id, entries in self._observability_records.items()
            },
            "sessions": {
                session_id: session.model_dump(mode="json")
                for session_id, session in self._sessions.items()
            },
            "runs": {
                session_id: run.model_dump(mode="json")
                for session_id, run in self._runs.items()
            },
            "stories": {
                story_id: story.model_dump(mode="json")
                for story_id, story in self._stories.items()
            },
            "environments": {
                session_id: environment.snapshot()
                for session_id, environment in self._environments.items()
            },
        }
        self._state_backend.save_state(payload)

    def get_storage_health(self) -> dict[str, object]:
        return self._state_backend.health()

    def get_database_overview(self) -> dict[str, object]:
        if not hasattr(self._state_backend, "get_database_overview"):
            raise KeyError("Database overview is not available for the active storage backend")
        return self._state_backend.get_database_overview()

    def list_database_table_rows(self, table_name: str, limit: int = 50) -> list[dict[str, object]]:
        if not hasattr(self._state_backend, "list_table_rows"):
            raise KeyError("Database table inspection is not available for the active storage backend")
        return self._state_backend.list_table_rows(table_name, limit=limit)

    def get_database_migration_status(self) -> dict[str, object]:
        if not hasattr(self._state_backend, "get_migration_status"):
            raise KeyError("Database migrations are not available for the active storage backend")
        return self._state_backend.get_migration_status()

    def _normalize_email(self, email: str) -> str:
        return email.strip().lower()

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _to_auth_account(self, account: StoredAuthAccount) -> AuthAccount:
        return AuthAccount(
            account_id=account.account_id,
            name=account.name,
            email=account.email,
            team=account.team,
            created_at=account.created_at,
        )

    def _write_auth_account(self, account: StoredAuthAccount) -> None:
        self._state_backend.upsert_auth_account(account.model_dump(mode="json"))

    def _write_auth_tokens(self) -> None:
        self._state_backend.replace_auth_tokens(self._auth_tokens)

    def _write_project(self, project: ProjectConfig) -> None:
        self._state_backend.upsert_project(project.model_dump(mode="json"))

    def _write_story(self, story: UserStoryRecord) -> None:
        self._state_backend.upsert_story(story.model_dump(mode="json"))

    def _write_run(self, run: IncidentRun) -> None:
        self._state_backend.upsert_run(run.model_dump(mode="json"))

    def _write_logs(self, project_id: str, entries: list[ProjectLogEntry]) -> None:
        self._state_backend.append_project_logs(
            project_id,
            [entry.model_dump(mode="json") for entry in entries],
        )

    def _write_metrics(self, project_id: str, entries: list[ProjectMetricPoint]) -> None:
        self._state_backend.append_project_metrics(
            project_id,
            [entry.model_dump(mode="json") for entry in entries],
        )

    def _write_event(self, event: ProjectEvent) -> None:
        self._state_backend.append_project_event(event.model_dump(mode="json"))

    def _write_monitor(self, monitor: WebsiteMonitorConfig) -> None:
        self._state_backend.upsert_monitor(monitor.project_id, monitor.model_dump(mode="json"))

    def _write_monitor_trigger(self, project_id: str, trigger: MonitorIncidentTrigger) -> None:
        self._state_backend.upsert_monitor_trigger(project_id, trigger.model_dump(mode="json"))

    def _write_health_snapshot(self, snapshot: WebsiteHealthSnapshot) -> None:
        self._state_backend.upsert_health_snapshot(snapshot.model_dump(mode="json"))

    def _write_validation_snapshot(self, snapshot: ProjectValidationSnapshot) -> None:
        self._state_backend.append_validation_snapshot(snapshot.model_dump(mode="json"))

    def _write_test_environment_config(self, config: TestEnvironmentConfig) -> None:
        self._state_backend.upsert_test_environment_config(config.project_id, config.model_dump(mode="json"))

    def _write_test_environment_run(self, result: TestEnvironmentRunResult) -> None:
        self._state_backend.append_test_environment_run(result.project_id, result.model_dump(mode="json"))

    def register_account(self, request: AuthRegisterRequest) -> AuthAccount:
        name = request.name.strip()
        email = self._normalize_email(request.email)
        password = request.password

        if not name:
            raise ValueError("Account name is required")
        if not email:
            raise ValueError("Email is required")
        if not password:
            raise ValueError("Password is required")
        if email in self._auth_email_index:
            raise ValueError("An account with this email already exists")

        account = StoredAuthAccount(
            account_id=uuid4().hex,
            name=name,
            email=email,
            team=request.team.strip(),
            password_hash=self._hash_password(password),
        )
        self._auth_accounts[account.account_id] = account
        self._auth_email_index[email] = account.account_id
        self._write_auth_account(account)
        self._save()
        return self._to_auth_account(account)

    def login_account(self, request: AuthLoginRequest) -> AuthLoginResponse:
        email = self._normalize_email(request.email)
        account_id = self._auth_email_index.get(email)
        if account_id is None:
            raise ValueError("Invalid email or password")

        account = self._auth_accounts.get(account_id)
        if account is None:
            raise ValueError("Invalid email or password")
        if account.password_hash != self._hash_password(request.password):
            raise ValueError("Invalid email or password")

        self._auth_tokens = {
            token: value
            for token, value in self._auth_tokens.items()
            if value != account.account_id
        }
        token = uuid4().hex
        self._auth_tokens[token] = account.account_id
        self._write_auth_tokens()
        self._save()
        return AuthLoginResponse(token=token, account=self._to_auth_account(account))

    def get_account_from_token(self, token: str) -> AuthAccount:
        account_id = self._auth_tokens.get(token)
        if account_id is None:
            raise KeyError("Invalid authentication token")
        account = self._auth_accounts.get(account_id)
        if account is None:
            raise KeyError("Invalid authentication token")
        return self._to_auth_account(account)

    def logout_token(self, token: str) -> None:
        if token in self._auth_tokens:
            del self._auth_tokens[token]
            self._state_backend.remove_auth_token(token)
            self._write_auth_tokens()
            self._save()

    def _normalize_base_url(self, base_url: str | None) -> str | None:
        normalized = (base_url or "").strip()
        if not normalized:
            return None
        return normalized.rstrip("/")

    def _normalize_healthcheck_path(self, path: str | None, fallback: str = "/health") -> str:
        value = (path or "").strip()
        if not value:
            return fallback
        return value if value.startswith("/") else f"/{value}"

    def _normalize_endpoint_id(self, raw_value: str | None, fallback_index: int) -> str:
        value = (raw_value or "").strip().lower()
        if not value:
            value = f"endpoint-{fallback_index}"
        value = re.sub(r"[^a-z0-9_-]+", "-", value).strip("-")
        return value or f"endpoint-{fallback_index}"

    def _build_project_endpoints(
        self,
        *,
        request_endpoints: list[ProjectEndpointInput] | None,
        base_url: str | None,
        healthcheck_path: str,
    ) -> list[ProjectEndpoint]:
        endpoints: list[ProjectEndpoint] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(request_endpoints or [], start=1):
            endpoint_base_url = self._normalize_base_url(item.base_url)
            if not endpoint_base_url:
                continue
            endpoint_id_seed = self._normalize_endpoint_id(item.endpoint_id, fallback_index=index)
            endpoint_id = endpoint_id_seed
            suffix = 2
            while endpoint_id in seen_ids:
                endpoint_id = f"{endpoint_id_seed}-{suffix}"
                suffix += 1
            seen_ids.add(endpoint_id)
            endpoints.append(
                ProjectEndpoint(
                    endpoint_id=endpoint_id,
                    label=(item.label.strip() if item.label else endpoint_id),
                    base_url=endpoint_base_url,
                    surface=(item.surface or "general").strip().lower() or "general",
                    healthcheck_path=self._normalize_healthcheck_path(item.healthcheck_path, fallback=healthcheck_path),
                    metadata=item.metadata,
                )
            )

        normalized_project_base = self._normalize_base_url(base_url)
        if normalized_project_base:
            matching = next((endpoint for endpoint in endpoints if endpoint.base_url == normalized_project_base), None)
            if matching is None:
                endpoint_id = "primary"
                suffix = 2
                while endpoint_id in seen_ids:
                    endpoint_id = f"primary-{suffix}"
                    suffix += 1
                seen_ids.add(endpoint_id)
                endpoints.insert(
                    0,
                    ProjectEndpoint(
                        endpoint_id=endpoint_id,
                        label="Primary",
                        base_url=normalized_project_base,
                        surface="general",
                        healthcheck_path=healthcheck_path,
                    ),
                )
        elif endpoints:
            normalized_project_base = endpoints[0].base_url

        return endpoints

    def _ensure_project_endpoint_defaults(self, project: ProjectConfig) -> ProjectConfig:
        normalized_base = self._normalize_base_url(project.base_url)
        if normalized_base != project.base_url:
            project.base_url = normalized_base

        if project.endpoints:
            normalized: list[ProjectEndpoint] = []
            seen: set[str] = set()
            for index, endpoint in enumerate(project.endpoints, start=1):
                endpoint_base_url = self._normalize_base_url(endpoint.base_url)
                if not endpoint_base_url:
                    continue
                endpoint_id = self._normalize_endpoint_id(endpoint.endpoint_id, fallback_index=index)
                suffix = 2
                while endpoint_id in seen:
                    endpoint_id = f"{endpoint_id}-{suffix}"
                    suffix += 1
                seen.add(endpoint_id)
                normalized.append(
                    endpoint.model_copy(
                        update={
                            "endpoint_id": endpoint_id,
                            "base_url": endpoint_base_url,
                            "surface": (endpoint.surface or "general").strip().lower() or "general",
                            "healthcheck_path": self._normalize_healthcheck_path(
                                endpoint.healthcheck_path,
                                fallback=project.healthcheck_path,
                            ),
                        }
                    )
                )
            project.endpoints = normalized
            if not project.base_url and normalized:
                project.base_url = normalized[0].base_url
        elif project.base_url:
            project.endpoints = [
                ProjectEndpoint(
                    endpoint_id="primary",
                    label="Primary",
                    base_url=project.base_url,
                    surface="general",
                    healthcheck_path=self._normalize_healthcheck_path(project.healthcheck_path),
                )
            ]

        return project

    def resolve_project_endpoint(
        self,
        project_id: str,
        *,
        endpoint_id: str | None = None,
        preferred_surface: str | None = None,
    ) -> ProjectEndpoint | None:
        project = self.get_project(project_id)
        endpoints = list(project.endpoints)
        if endpoint_id:
            target = endpoint_id.strip().lower()
            for endpoint in endpoints:
                if endpoint.endpoint_id.lower() == target:
                    return endpoint
            raise KeyError(f"Unknown endpoint_id '{endpoint_id}' for project_id: {project_id}")

        if preferred_surface:
            surface = preferred_surface.strip().lower()
            for endpoint in endpoints:
                if endpoint.surface.strip().lower() == surface:
                    return endpoint

        if project.base_url:
            matching = next((endpoint for endpoint in endpoints if endpoint.base_url == project.base_url), None)
            if matching:
                return matching
            return ProjectEndpoint(
                endpoint_id="primary",
                label="Primary",
                base_url=project.base_url,
                surface="general",
                healthcheck_path=self._normalize_healthcheck_path(project.healthcheck_path),
            )

        if endpoints:
            return endpoints[0]
        return None

    def create_project(self, request: ProjectCreateRequest) -> ProjectConfig:
        base_url = self._normalize_base_url(request.base_url)
        repository_url = (request.repository_url or "").strip() or None
        healthcheck_path = self._normalize_healthcheck_path(request.healthcheck_path)
        endpoints = self._build_project_endpoints(
            request_endpoints=request.endpoints,
            base_url=base_url,
            healthcheck_path=healthcheck_path,
        )
        if not base_url and endpoints:
            base_url = endpoints[0].base_url
        project = ProjectConfig(
            project_id=request.project_id or uuid4().hex,
            name=request.name.strip(),
            base_url=base_url,
            repository_url=repository_url,
            healthcheck_path=healthcheck_path,
            endpoints=endpoints,
            metadata=request.metadata,
        )
        project = self._ensure_project_endpoint_defaults(project)
        self._projects[project.project_id] = project
        self._write_project(project)
        self._project_agents[project.project_id] = self._build_default_agents(project.project_id)
        self._agent_coordination.setdefault(project.project_id, [])
        self._agent_conversations.setdefault(project.project_id, [])
        self._record_event(
            project.project_id,
            event_type="project_created",
            title="Project registered",
            message=f"{project.name} was registered with OpenIncident.",
            severity="info",
            source="project",
            persist=False,
        )
        self._save()
        return project

    def _record_event(
        self,
        project_id: str,
        *,
        event_type: str,
        title: str,
        message: str,
        severity: str = "info",
        source: str = "system",
        related_run_id: str | None = None,
        related_session_id: str | None = None,
        related_story_id: str | None = None,
        metadata: dict | None = None,
        persist: bool = True,
    ) -> ProjectEvent:
        event = ProjectEvent(
            event_id=uuid4().hex,
            project_id=project_id,
            event_type=event_type,
            title=title,
            message=message,
            severity=severity,
            source=source,
            related_run_id=related_run_id,
            related_session_id=related_session_id,
            related_story_id=related_story_id,
            metadata=metadata or {},
        )
        self._project_events.setdefault(project_id, []).append(event)
        self._write_event(event)
        if persist:
            self._save()
        return event

    def _record_agent_handoff(
        self,
        project_id: str,
        *,
        to_role: AgentRole,
        handoff_type: str,
        summary: str,
        from_role: AgentRole | None = None,
        related_story_id: str | None = None,
        related_run_id: str | None = None,
        related_session_id: str | None = None,
        metadata: dict | None = None,
        persist: bool = True,
    ) -> AgentCoordinationEntry:
        self.get_project(project_id)
        entry = AgentCoordinationEntry(
            entry_id=uuid4().hex,
            project_id=project_id,
            from_role=from_role,
            to_role=to_role,
            handoff_type=handoff_type,
            summary=summary,
            related_story_id=related_story_id,
            related_run_id=related_run_id,
            related_session_id=related_session_id,
            metadata=metadata or {},
        )
        self._agent_coordination.setdefault(project_id, []).append(entry)
        self._record_event(
            project_id,
            event_type="agent_handoff",
            title="Agent handoff recorded",
            message=summary,
            severity="info",
            source="agents",
            related_run_id=related_run_id,
            related_session_id=related_session_id,
            related_story_id=related_story_id,
            metadata={
                "handoff_type": handoff_type,
                "from_role": from_role.value if from_role else None,
                "to_role": to_role.value,
                **(metadata or {}),
            },
            persist=False,
        )
        if persist:
            self._save()
        return entry

    def _record_agent_message(
        self,
        project_id: str,
        *,
        sender_role: AgentRole,
        content: str,
        recipient_role: AgentRole | None = None,
        message_type: str = "handoff_note",
        related_story_id: str | None = None,
        related_run_id: str | None = None,
        related_session_id: str | None = None,
        metadata: dict | None = None,
        persist: bool = True,
    ) -> AgentConversationMessage:
        self.get_project(project_id)
        message = AgentConversationMessage(
            message_id=uuid4().hex,
            project_id=project_id,
            sender_role=sender_role,
            recipient_role=recipient_role,
            message_type=message_type,
            content=content,
            related_story_id=related_story_id,
            related_run_id=related_run_id,
            related_session_id=related_session_id,
            metadata=metadata or {},
        )
        self._agent_conversations.setdefault(project_id, []).append(message)
        if persist:
            self._save()
        return message

    def create_user_story(self, project_id: str, story_input: UserStoryInput) -> UserStoryRecord:
        self.get_project(project_id)
        story = UserStoryRecord(
            story_id=story_input.story_id or uuid4().hex,
            project_id=project_id,
            title=story_input.title,
            description=story_input.description,
            acceptance_criteria=story_input.acceptance_criteria,
            tags=story_input.tags,
            hints=story_input.hints,
        )
        self._stories[story.story_id] = story
        self._write_story(story)
        self._record_event(
            project_id,
            event_type="story_created",
            title="User story added",
            message=story.title,
            severity="info",
            source="story",
            related_story_id=story.story_id,
            persist=False,
        )
        self._save()
        return story

    def create_user_stories(self, project_id: str, request: UserStoryBatchCreateRequest) -> list[UserStoryRecord]:
        return [self.create_user_story(project_id, story_input) for story_input in request.stories]

    def list_project_stories(self, project_id: str) -> list[UserStoryRecord]:
        self.get_project(project_id)
        stories = [story for story in self._stories.values() if story.project_id == project_id]
        return sorted(stories, key=lambda story: story.updated_at, reverse=True)

    def get_story(self, story_id: str) -> UserStoryRecord:
        try:
            return self._stories[story_id]
        except KeyError as exc:
            raise KeyError(f"Unknown story_id: {story_id}") from exc

    def analyze_story(self, story_id: str) -> UserStoryRecord:
        story = self.get_story(story_id)
        story.analysis = analyze_story(story)
        if story.status == StoryStatus.PENDING:
            story.status = StoryStatus.ANALYZED
        story.updated_at = datetime.now(timezone.utc)
        self._stories[story_id] = story
        self._write_story(story)
        self._record_event(
            story.project_id,
            event_type="story_analyzed",
            title="Story analyzed",
            message=f"{story.title} was classified as {story.analysis.primary_domain.value}.",
            severity="info",
            source="story",
            related_story_id=story.story_id,
            metadata={
                "primary_domain": story.analysis.primary_domain.value,
                "assigned_agent": story.analysis.assigned_agent.value,
                "confidence_score": story.analysis.confidence_score,
                "execution_priority": story.analysis.execution_priority.value,
            },
            persist=False,
        )
        self._update_agent_activity(
            story.project_id,
            AgentRole.PLANNER,
            success=True,
            note=f"Classified story '{story.title}' into {story.analysis.primary_domain.value}.",
        )
        self._record_agent_handoff(
            story.project_id,
            from_role=AgentRole.PLANNER,
            to_role=story.analysis.assigned_agent,
            handoff_type="story_analysis",
            summary=f"Planner routed '{story.title}' to {story.analysis.assigned_agent.value}.",
            related_story_id=story.story_id,
            metadata={
                "primary_domain": story.analysis.primary_domain.value,
                "suggested_tests": [item.value for item in story.analysis.suggested_test_types],
                "confidence_score": story.analysis.confidence_score,
                "execution_priority": story.analysis.execution_priority.value,
            },
            persist=False,
        )
        self._record_agent_message(
            story.project_id,
            sender_role=AgentRole.PLANNER,
            recipient_role=story.analysis.assigned_agent,
            message_type="planning_note",
            content=(
                f"I classified '{story.title}' as {story.analysis.primary_domain.value} and routed it to "
                f"{story.analysis.assigned_agent.value} with suggested tests "
                f"{', '.join(item.value for item in story.analysis.suggested_test_types) or 'none'}. "
                f"Confidence {story.analysis.confidence_score:.0%}, priority {story.analysis.execution_priority.value}."
            ),
            related_story_id=story.story_id,
            metadata={
                "reasoning": story.analysis.reasoning,
                "planning_notes": story.analysis.planning_notes,
            },
            persist=False,
        )
        self._save()
        return story

    def attach_story_execution_result(self, story_id: str, result: UserStoryExecutionResult) -> UserStoryRecord:
        story = self.get_story(story_id)
        story.latest_result = result
        story.status = result.status
        story.updated_at = datetime.now(timezone.utc)
        self._stories[story_id] = story
        self._write_story(story)
        self._record_event(
            story.project_id,
            event_type="story_executed",
            title=f"Story {result.status.value}",
            message=result.summary,
            severity="error" if result.status == StoryStatus.FAILED else "info",
            source="story",
            related_story_id=story.story_id,
            related_run_id=result.linked_run_id,
            related_session_id=result.linked_session_id,
            metadata={"test_type": result.test_type.value, "success": result.success},
            persist=False,
        )
        role = story.analysis.assigned_agent if story.analysis else AgentRole.PLANNER
        self._update_agent_activity(
            story.project_id,
            role,
            success=result.success,
            note=f"Executed story '{story.title}' with {result.test_type.value}.",
            story_validated=True,
        )
        self._record_agent_handoff(
            story.project_id,
            from_role=role,
            to_role=AgentRole.OVERSIGHT if result.success else AgentRole.RELIABILITY_ANALYST,
            handoff_type="story_execution",
            summary=(
                f"{role.value} completed '{story.title}' and handed results to "
                f"{'oversight' if result.success else 'reliability_analyst'}."
            ),
            related_story_id=story.story_id,
            related_run_id=result.linked_run_id,
            related_session_id=result.linked_session_id,
            metadata={"success": result.success, "test_type": result.test_type.value},
            persist=False,
        )
        self._record_agent_message(
            story.project_id,
            sender_role=role,
            recipient_role=AgentRole.OVERSIGHT if result.success else AgentRole.RELIABILITY_ANALYST,
            message_type="execution_result",
            content=(
                f"I executed '{story.title}' using {result.test_type.value}. "
                f"Result: {'success' if result.success else 'failure'}. Summary: {result.summary}"
            ),
            related_story_id=story.story_id,
            related_run_id=result.linked_run_id,
            related_session_id=result.linked_session_id,
            metadata={"evidence_count": len(result.evidence)},
            persist=False,
        )
        self._save()
        return story

    def build_story_report(self, project_id: str) -> ProjectStoryReport:
        return build_story_report(project_id, self.list_project_stories(project_id))

    def build_planner_summary(self, project_id: str):
        return build_planner_summary(project_id, self.list_project_stories(project_id))

    def build_planner_training_dataset(self, project_id: str):
        return build_planner_training_dataset(project_id, self.list_project_stories(project_id))

    def build_frontend_training_dataset(self, project_id: str):
        project = self.get_project(project_id)
        workspace_path = self.get_latest_test_environment_workspace(project_id)
        return build_frontend_training_dataset(project, self.list_project_stories(project_id), workspace_path=workspace_path)

    def build_api_training_dataset(self, project_id: str):
        self.get_project(project_id)
        return build_api_training_dataset(project_id, self.list_project_stories(project_id))

    def build_guardian_training_dataset(self, project_id: str) -> ProjectGuardianTrainingDataset:
        self.get_project(project_id)
        records = sorted(self._guardian_decisions.get(project_id, []), key=lambda item: item.completed_at, reverse=True)
        total = len(records)
        ready = sum(record.release_ready for record in records)
        blocked = total - ready
        with_open_incidents = sum(record.open_incident_count > 0 for record in records)
        healthy_ready = sum(
            record.release_ready and record.open_incident_count == 0 and (record.latest_check_status in {None, "healthy"})
            for record in records
        )
        return ProjectGuardianTrainingDataset(
            project_id=project_id,
            total_decisions=total,
            ready_decisions=ready,
            blocked_decisions=blocked,
            decisions_with_open_incidents=with_open_incidents,
            healthy_ready_rate=round(healthy_ready / total, 4) if total else 0.0,
            records=records,
        )

    def record_triage_summary(self, project_id: str, run: IncidentRun, result: RunTriageSummary) -> TriageTrainingRecord:
        observation = run.last_observation
        record = TriageTrainingRecord(
            triage_id=uuid4().hex,
            project_id=project_id,
            run_id=run.run_id,
            session_id=run.session_id,
            task_id=run.task_id,
            run_status=run.status,
            incident_source=run.source,
            confidence=result.confidence,
            suspected_root_cause=result.suspected_root_cause,
            summary=result.summary,
            evidence_count=len(result.evidence),
            recommendation_count=len(result.recommended_actions),
            recommended_action_types=[item.action_type for item in result.recommended_actions],
            open_incident_count=sum(item.status != "resolved" for item in self.list_runs(project_id)),
            service_restored=bool(observation.service_restored) if observation else False,
            root_cause_confirmed=bool(observation.root_cause_confirmed) if observation else False,
        )
        self._triage_records.setdefault(project_id, []).append(record)
        self._save()
        return record

    def build_triage_training_dataset(self, project_id: str) -> ProjectTriageTrainingDataset:
        self.get_project(project_id)
        records = sorted(self._triage_records.get(project_id, []), key=lambda item: item.generated_at, reverse=True)
        total = len(records)
        average_confidence = round(sum(record.confidence for record in records) / total, 4) if total else 0.0
        restored_rate = round(sum(record.service_restored for record in records) / total, 4) if total else 0.0
        root_cause_rate = round(sum(record.root_cause_confirmed for record in records) / total, 4) if total else 0.0
        recommendation_rate = round(sum(record.recommendation_count > 0 for record in records) / total, 4) if total else 0.0
        return ProjectTriageTrainingDataset(
            project_id=project_id,
            total_triages=total,
            average_confidence=average_confidence,
            restored_triage_rate=restored_rate,
            root_cause_confirmed_rate=root_cause_rate,
            recommendation_coverage_rate=recommendation_rate,
            records=records,
        )

    def build_observability_training_dataset(self, project_id: str) -> ProjectObservabilityTrainingDataset:
        self.get_project(project_id)
        records = sorted(self._observability_records.get(project_id, []), key=lambda item: item.generated_at, reverse=True)
        total = len(records)
        unhealthy_records = sum(record.status in {"unhealthy", "unreachable"} for record in records)
        healthy_records = sum(record.status == "healthy" for record in records)
        with_log_errors = sum(record.log_error_entries > 0 for record in records)
        with_degraded_metrics = sum(bool(record.degraded_metrics) for record in records)
        incident_link_rate = round(sum(record.active_incident_count > 0 for record in records) / total, 4) if total else 0.0
        return ProjectObservabilityTrainingDataset(
            project_id=project_id,
            total_records=total,
            unhealthy_records=unhealthy_records,
            healthy_records=healthy_records,
            records_with_log_errors=with_log_errors,
            records_with_degraded_metrics=with_degraded_metrics,
            incident_link_rate=incident_link_rate,
            records=records,
        )

    def build_oversight_training_dataset(self, project_id: str) -> ProjectOversightTrainingDataset:
        self.get_project(project_id)
        coordination_entries = self.list_agent_coordination(project_id)
        audit_entries = [
            entry
            for entry in coordination_entries
            if entry.to_role == AgentRole.OVERSIGHT or entry.from_role == AgentRole.OVERSIGHT
        ]

        records: list[OversightAuditRecord] = []
        run_linked = 0
        story_linked = 0
        resolved_run_audits = 0
        completed_story_audits = 0

        for entry in sorted(audit_entries, key=lambda item: item.timestamp, reverse=True):
            linked_story = self._stories.get(entry.related_story_id) if entry.related_story_id else None
            linked_run = self.get_run_by_id(entry.related_run_id) if entry.related_run_id else None
            confidence_signal = None
            if isinstance(entry.metadata, dict):
                raw_confidence = entry.metadata.get("confidence")
                if isinstance(raw_confidence, (int, float)):
                    confidence_signal = float(raw_confidence)

            run_linked += int(linked_run is not None)
            story_linked += int(linked_story is not None)
            resolved_run_audits += int(linked_run is not None and linked_run.status == "resolved")
            completed_story_audits += int(linked_story is not None and linked_story.status == StoryStatus.COMPLETED)

            records.append(
                OversightAuditRecord(
                    audit_id=entry.entry_id,
                    project_id=project_id,
                    timestamp=entry.timestamp,
                    source_role=entry.from_role,
                    audit_type=entry.handoff_type,
                    summary=entry.summary,
                    related_story_id=entry.related_story_id,
                    related_run_id=entry.related_run_id,
                    related_session_id=entry.related_session_id,
                    linked_story_status=linked_story.status if linked_story else None,
                    linked_run_status=linked_run.status if linked_run else None,
                    confidence_signal=confidence_signal,
                    metadata=entry.metadata,
                )
            )

        total = len(records)
        return ProjectOversightTrainingDataset(
            project_id=project_id,
            total_audits=total,
            run_linked_audits=run_linked,
            story_linked_audits=story_linked,
            resolved_run_audit_rate=round(resolved_run_audits / run_linked, 4) if run_linked else 0.0,
            completed_story_audit_rate=round(completed_story_audits / story_linked, 4) if story_linked else 0.0,
            records=records,
        )

    def list_projects(self, owner_account_id: str | None = None) -> list[ProjectConfig]:
        projects = [self._ensure_project_endpoint_defaults(project) for project in self._projects.values()]
        if owner_account_id is None:
            return projects
        return [
            project
            for project in projects
            if project.metadata.get("owner_id") == owner_account_id
        ]

    def add_project_logs(self, project_id: str, request: ProjectLogBatchRequest) -> list[ProjectLogEntry]:
        self.get_project(project_id)
        created_entries = create_log_entries(project_id, request)
        self._project_logs.setdefault(project_id, []).extend(created_entries)
        self._write_logs(project_id, created_entries)
        self._record_event(
            project_id,
            event_type="logs_ingested",
            title="Runtime logs ingested",
            message=f"{len(created_entries)} log entr{'y' if len(created_entries) == 1 else 'ies'} added.",
            severity="warning" if any(entry.level.upper() in {"ERROR", "WARNING"} for entry in created_entries) else "info",
            source="logs",
            metadata={"count": len(created_entries)},
            persist=False,
        )
        self._save()
        return created_entries

    def list_project_logs(self, project_id: str) -> list[ProjectLogEntry]:
        self.get_project(project_id)
        return sorted(self._project_logs.get(project_id, []), key=lambda entry: entry.timestamp, reverse=True)

    def get_project_log_summary(self, project_id: str) -> ProjectLogSummary:
        return summarize_logs(project_id, self.list_project_logs(project_id))

    def set_project_log_connector(self, project_id: str, request: ProjectLogConnectorRequest) -> ProjectLogConnectorConfig:
        self.get_project(project_id)
        config = ProjectLogConnectorConfig(
            project_id=project_id,
            url=request.url.strip(),
            method=request.method.upper(),
            headers=request.headers,
            enabled=request.enabled,
            format=request.format.lower(),
            entries_path=request.entries_path,
            level_field=request.level_field,
            source_field=request.source_field,
            message_field=request.message_field,
            timestamp_field=request.timestamp_field,
        )
        self._log_connectors[project_id] = config
        self._record_event(
            project_id,
            event_type="log_connector_configured",
            title="Log connector configured",
            message=f"Remote log pull is now {'enabled' if config.enabled else 'disabled'} for {config.url}.",
            severity="info",
            source="logs",
            metadata={"url": config.url, "format": config.format, "enabled": config.enabled},
            persist=False,
        )
        self._save()
        return config

    def get_project_log_connector(self, project_id: str) -> ProjectLogConnectorConfig:
        self.get_project(project_id)
        try:
            return self._log_connectors[project_id]
        except KeyError as exc:
            raise KeyError(f"No log connector configured for project_id: {project_id}") from exc

    def pull_project_logs_from_connector(self, project_id: str, limit: int = 100) -> ProjectLogConnectorPullResult:
        config = self.get_project_log_connector(project_id)
        if not config.enabled:
            return ProjectLogConnectorPullResult(
                project_id=project_id,
                success=False,
                summary="Log connector is disabled for this project.",
                error_message="Connector disabled",
            )

        entries, result = pull_logs_from_connector(project_id, config, limit=limit)
        if entries:
            created_entries = create_log_entries(project_id, ProjectLogBatchRequest(entries=entries))
            self._project_logs.setdefault(project_id, []).extend(created_entries)
            self._write_logs(project_id, created_entries)
            result.imported_entries = len(created_entries)
            config.last_pulled_at = result.pulled_at
            self._log_connectors[project_id] = config
            self._record_event(
                project_id,
                event_type="log_connector_pull",
                title="Remote logs pulled",
                message=result.summary,
                severity="warning" if any(entry.level.upper() in {"ERROR", "WARNING"} for entry in created_entries) else "info",
                source="logs",
                metadata={"count": len(created_entries), "url": config.url},
                persist=False,
            )
            self._save()
        return result

    def add_project_metrics(self, project_id: str, request: ProjectMetricBatchRequest) -> list[ProjectMetricPoint]:
        self.get_project(project_id)
        created_points = [
            ProjectMetricPoint(
                metric_id=uuid4().hex,
                project_id=project_id,
                timestamp=point.timestamp or datetime.now(timezone.utc),
                name=point.name,
                value=point.value,
                unit=point.unit,
                source=point.source,
                dimensions=point.dimensions,
            )
            for point in request.points
        ]
        self._project_metrics.setdefault(project_id, []).extend(created_points)
        self._write_metrics(project_id, created_points)
        self._record_event(
            project_id,
            event_type="metrics_ingested",
            title="Metrics ingested",
            message=f"{len(created_points)} metric point{'s' if len(created_points) != 1 else ''} added.",
            severity="info",
            source="metrics",
            metadata={"count": len(created_points)},
            persist=False,
        )
        self._save()
        return created_points

    def list_project_metrics(self, project_id: str) -> list[ProjectMetricPoint]:
        self.get_project(project_id)
        return sorted(self._project_metrics.get(project_id, []), key=lambda entry: entry.timestamp, reverse=True)

    def get_project_metric_summary(self, project_id: str) -> ProjectMetricSummary:
        points = self.list_project_metrics(project_id)
        by_name: dict[str, list[ProjectMetricPoint]] = {}
        for point in points:
            by_name.setdefault(point.name, []).append(point)

        series: list[ProjectMetricSeries] = []
        latest_values: dict[str, float] = {}
        units: dict[str, str] = {}
        degraded_metrics: list[str] = []
        degradation_keywords = ("error", "latency", "timeout", "cpu", "memory", "queue", "failure")

        for name, entries in sorted(by_name.items()):
            latest = entries[0]
            series.append(
                ProjectMetricSeries(
                    name=name,
                    latest_value=latest.value,
                    latest_unit=latest.unit,
                    latest_source=latest.source,
                    points=entries[:20],
                )
            )
            latest_values[name] = latest.value
            if latest.unit:
                units[name] = latest.unit
            lowered = name.lower()
            if any(keyword in lowered for keyword in degradation_keywords):
                degraded_metrics.append(name)

        return ProjectMetricSummary(
            project_id=project_id,
            total_points=len(points),
            latest_values=latest_values,
            units=units,
            degraded_metrics=degraded_metrics,
            series=series,
        )

    def list_project_events(self, project_id: str, limit: int | None = None) -> list[ProjectEvent]:
        self.get_project(project_id)
        events = sorted(self._project_events.get(project_id, []), key=lambda event: event.timestamp, reverse=True)
        return events[:limit] if limit is not None else events

    def get_project_agent_roster(self, project_id: str) -> ProjectAgentRoster:
        self.get_project(project_id)
        agents = sorted(
            self._project_agents.setdefault(project_id, self._build_default_agents(project_id)),
            key=lambda agent: agent.role.value,
        )
        return ProjectAgentRoster(project_id=project_id, agents=agents)

    def set_test_environment_config(self, project_id: str, request: TestEnvironmentConfigRequest) -> TestEnvironmentConfig:
        project = self.get_project(project_id)
        config = TestEnvironmentConfig(
            project_id=project_id,
            repository_url=request.repository_url or project.repository_url or "",
            branch=request.branch,
            install_command=request.install_command,
            test_command=request.test_command,
            workdir=request.workdir,
            enabled=request.enabled,
            shell=request.shell,
            env=request.env,
        )
        self._test_env_configs[project_id] = config
        self._write_test_environment_config(config)
        self._record_event(
            project_id,
            event_type="test_environment_configured",
            title="Testing environment configured",
            message=f"Repo-driven testing is now {'enabled' if config.enabled else 'disabled'} for this project.",
            severity="info",
            source="testing",
            metadata={"branch": config.branch, "workdir": config.workdir, "test_command": config.test_command},
            persist=False,
        )
        self._save()
        return config

    def get_test_environment_config(self, project_id: str) -> TestEnvironmentConfig:
        self.get_project(project_id)
        try:
            return self._test_env_configs[project_id]
        except KeyError as exc:
            raise KeyError(f"No testing environment configured for project_id: {project_id}") from exc

    def add_test_environment_run(self, project_id: str, result: TestEnvironmentRunResult) -> TestEnvironmentRunResult:
        self.get_project(project_id)
        self._test_env_runs.setdefault(project_id, []).append(result)
        self._write_test_environment_run(result)
        self._record_event(
            project_id,
            event_type="test_environment_run",
            title="Repository test environment executed",
            message=result.summary,
            severity="info" if result.success else "error",
            source="testing",
            metadata={
                "workspace_path": result.workspace_path,
                "run_install": result.run_install,
                "run_tests": result.run_tests,
            },
            persist=False,
        )
        self._update_agent_activity(
            project_id,
            AgentRole.TEST_ENV_GUARDIAN,
            success=result.success,
            note=result.summary,
        )
        self._record_agent_handoff(
            project_id,
            from_role=AgentRole.TEST_ENV_GUARDIAN,
            to_role=AgentRole.OVERSIGHT if result.success else AgentRole.RELIABILITY_ANALYST,
            handoff_type="test_environment_run",
            summary=(
                "Test Environment Guardian completed repository validation and handed the result to "
                f"{'oversight' if result.success else 'reliability_analyst'}."
            ),
            related_run_id=result.linked_run_id,
            related_session_id=result.linked_session_id,
            metadata={
                "workspace_path": result.workspace_path,
                "success": result.success,
                "run_tests": result.run_tests,
            },
            persist=False,
        )
        self._record_agent_message(
            project_id,
            sender_role=AgentRole.TEST_ENV_GUARDIAN,
            recipient_role=AgentRole.OVERSIGHT if result.success else AgentRole.RELIABILITY_ANALYST,
            message_type="test_environment_result",
            content=(
                f"Repository validation finished with {'success' if result.success else 'failure'}. "
                f"Workspace: {result.workspace_path}. Summary: {result.summary}"
            ),
            related_run_id=result.linked_run_id,
            related_session_id=result.linked_session_id,
            metadata={"repository_url": result.repository_url},
            persist=False,
        )
        self._save()
        return result

    def create_test_environment_incident(
        self,
        project_id: str,
        test_result: TestEnvironmentRunResult,
    ) -> tuple[SessionInfo, IncidentRun, ProductionIncidentEnv]:
        project = self.get_project(project_id)
        trigger = self.get_monitor_trigger(project_id)
        session, run, environment = self.create_session(
            task_id=trigger.failure_task_id,
            project=project,
            source="testing_environment",
            trigger_reason=test_result.summary,
        )
        environment.prepare_external_incident(
            project_name=project.name,
            trigger_reason=f"Repository test environment failed for {project.name}. {test_result.summary}",
            severity=trigger.severity,
            repository_url=project.repository_url,
            base_url=project.base_url,
        )
        excerpt = None
        if test_result.test_result:
            excerpt = test_result.test_result.stderr or test_result.test_result.stdout
        elif test_result.install_result:
            excerpt = test_result.install_result.stderr or test_result.install_result.stdout

        observation = environment.attach_external_signal(
            project_name=project.name,
            target_url=test_result.repository_url,
            status="unhealthy",
            check_type="test_environment",
            label="Repository test environment",
            response_time_ms=(test_result.test_result.duration_seconds * 1000.0) if test_result.test_result else None,
            error_message=test_result.summary,
            response_excerpt=excerpt[:300] if excerpt else None,
        )
        observation = environment.attach_test_environment_context(
            workspace_path=test_result.workspace_path,
            install_command=test_result.install_result.command if test_result.install_result else None,
            test_command=test_result.test_result.command if test_result.test_result else None,
            install_stdout=test_result.install_result.stdout if test_result.install_result else None,
            install_stderr=test_result.install_result.stderr if test_result.install_result else None,
            test_stdout=test_result.test_result.stdout if test_result.test_result else None,
            test_stderr=test_result.test_result.stderr if test_result.test_result else None,
        )
        run.last_observation = observation
        run.status = observation.current_status
        run.source_check_type = "test_environment"
        run.source_target_url = test_result.repository_url
        run.source_label = "Repository test environment"
        self._runs[session.session_id] = run
        self._record_event(
            project_id,
            event_type="incident_opened_from_test_environment",
            title="Testing environment incident opened",
            message=test_result.summary,
            severity="error",
            source="incident",
            related_run_id=run.run_id,
            related_session_id=session.session_id,
            metadata={"workspace_path": test_result.workspace_path, "repository_url": test_result.repository_url},
            persist=False,
        )
        self._record_agent_handoff(
            project_id,
            from_role=AgentRole.TEST_ENV_GUARDIAN,
            to_role=AgentRole.RELIABILITY_ANALYST,
            handoff_type="incident_escalation",
            summary="Test Environment Guardian escalated a failed repository run into an active incident.",
            related_run_id=run.run_id,
            related_session_id=session.session_id,
            metadata={"repository_url": test_result.repository_url, "workspace_path": test_result.workspace_path},
            persist=False,
        )
        self._record_agent_message(
            project_id,
            sender_role=AgentRole.TEST_ENV_GUARDIAN,
            recipient_role=AgentRole.RELIABILITY_ANALYST,
            message_type="incident_escalation_note",
            content=(
                f"I escalated a failed repository run into an incident. "
                f"Repo: {test_result.repository_url}. Summary: {test_result.summary}"
            ),
            related_run_id=run.run_id,
            related_session_id=session.session_id,
            metadata={"workspace_path": test_result.workspace_path},
            persist=False,
        )
        self._save()
        return session, run, environment

    def list_test_environment_runs(self, project_id: str) -> list[TestEnvironmentRunResult]:
        self.get_project(project_id)
        return sorted(self._test_env_runs.get(project_id, []), key=lambda item: item.completed_at, reverse=True)

    def get_latest_test_environment_workspace(self, project_id: str, require_success: bool = False) -> str | None:
        self.get_project(project_id)
        for item in self.list_test_environment_runs(project_id):
            if require_success and not item.success:
                continue
            if item.workspace_path:
                return item.workspace_path
        return None

    def build_environment_summary(self, project_id: str) -> ProjectEnvironmentSummary:
        project = self.get_project(project_id)
        config = self._test_env_configs.get(project_id)
        latest_run = next(iter(self.list_test_environment_runs(project_id)), None)
        workspace_path = latest_run.workspace_path if latest_run and latest_run.workspace_path else None

        framework = None
        app_root = None
        route_count = 0
        recommended_install_command = config.install_command if config else None
        recommended_test_command = config.test_command if config else None
        recommended_workdir = config.workdir if config else None
        notes: list[str] = []

        if workspace_path:
            insight = inspect_workspace(project.project_id, project.repository_url or "", workspace_path)
            framework = insight.framework
            app_root = insight.app_root
            route_count = insight.route_count
            recommended_install_command = recommended_install_command or insight.recommended_install_command
            recommended_test_command = recommended_test_command or insight.recommended_test_command
            recommended_workdir = recommended_workdir or insight.recommended_workdir
            notes.extend(insight.notes)
        else:
            notes.append("Pull the GitHub workspace to unlock framework discovery and setup recommendations.")

        next_actions: list[str] = []
        if not project.repository_url:
            next_actions.append("Connect a GitHub repository so the environment agent can prepare project context.")
        if project.repository_url and not workspace_path:
            next_actions.append("Pull the repository workspace before running deeper automated validation.")
        if workspace_path and not framework:
            next_actions.append("Review repository structure because the framework could not be inferred automatically.")
        if workspace_path and route_count == 0:
            next_actions.append("Run or review frontend discovery if this project should expose browser-routable pages.")
        if workspace_path and not recommended_test_command:
            next_actions.append("Set a test command so repository validation can run consistently.")
        if not next_actions:
            next_actions.append("Environment context looks ready. Continue with planner-routed validation.")

        return ProjectEnvironmentSummary(
            project_id=project_id,
            repository_url=project.repository_url,
            base_url=project.base_url,
            repository_connected=bool(project.repository_url),
            deployment_connected=bool(project.base_url),
            workspace_ready=bool(workspace_path),
            workspace_path=workspace_path,
            last_run_success=latest_run.success if latest_run else None,
            last_run_summary=latest_run.summary if latest_run else None,
            shell=config.shell if config else None,
            branch=config.branch if config else None,
            framework=framework,
            app_root=app_root,
            route_count=route_count,
            recommended_install_command=recommended_install_command,
            recommended_test_command=recommended_test_command,
            recommended_workdir=recommended_workdir,
            next_actions=next_actions,
            notes=notes,
        )

    def get_test_environment_run_for_incident(self, project_id: str, run_id: str | None = None, session_id: str | None = None) -> TestEnvironmentRunResult | None:
        runs = self._test_env_runs.get(project_id, [])
        for item in reversed(runs):
            if run_id and item.linked_run_id == run_id:
                return item
            if session_id and item.linked_session_id == session_id:
                return item
        return None

    def record_triage_activity(self, project_id: str, confidence: float, summary: str) -> AgentProfile:
        success = confidence >= 0.7
        agent = self._update_agent_activity(
            project_id,
            AgentRole.RELIABILITY_ANALYST,
            success=success,
            note=summary,
            incident_triaged=True,
        )
        self._update_agent_activity(
            project_id,
            AgentRole.OVERSIGHT,
            success=success,
            note=f"Oversight reviewed triage confidence at {round(confidence, 2)}.",
        )
        self._record_agent_handoff(
            project_id,
            from_role=AgentRole.RELIABILITY_ANALYST,
            to_role=AgentRole.OVERSIGHT,
            handoff_type="triage_review",
            summary="Reliability triage was handed to Oversight for confidence and closure review.",
            metadata={"confidence": round(confidence, 2), "success": success},
            persist=False,
        )
        self._record_agent_message(
            project_id,
            sender_role=AgentRole.RELIABILITY_ANALYST,
            recipient_role=AgentRole.OVERSIGHT,
            message_type="triage_note",
            content=f"I completed triage with confidence {round(confidence, 2)}. Summary: {summary}",
            metadata={"confidence": round(confidence, 2), "success": success},
            persist=False,
        )
        self._save()
        return agent

    def list_agent_coordination(self, project_id: str, limit: int | None = None) -> list[AgentCoordinationEntry]:
        self.get_project(project_id)
        entries = sorted(self._agent_coordination.get(project_id, []), key=lambda item: item.timestamp, reverse=True)
        return entries[:limit] if limit is not None else entries

    def get_project_agent_coordination_trace(self, project_id: str, limit: int | None = None) -> ProjectAgentCoordinationTrace:
        return ProjectAgentCoordinationTrace(
            project_id=project_id,
            entries=self.list_agent_coordination(project_id, limit=limit),
        )

    def list_agent_conversations(self, project_id: str, limit: int | None = None) -> list[AgentConversationMessage]:
        self.get_project(project_id)
        messages = sorted(self._agent_conversations.get(project_id, []), key=lambda item: item.timestamp, reverse=True)
        return messages[:limit] if limit is not None else messages

    def get_project_agent_conversation_trace(self, project_id: str, limit: int | None = None) -> ProjectAgentConversationTrace:
        return ProjectAgentConversationTrace(
            project_id=project_id,
            messages=self.list_agent_conversations(project_id, limit=limit),
        )

    def get_project_command_center_summary(self, project_id: str) -> ProjectCommandCenterSummary:
        project = self.get_project(project_id)
        latest_health = self._health_snapshots.get(project_id)
        checks = self.list_validation_snapshots(project_id)
        latest_check = checks[-1] if checks else None
        return ProjectCommandCenterSummary(
            project=project,
            agent_roster=self.get_project_agent_roster(project_id),
            coordination_trace=self.get_project_agent_coordination_trace(project_id, limit=25),
            conversation_trace=self.get_project_agent_conversation_trace(project_id, limit=25),
            latest_health=latest_health,
            latest_check=latest_check,
            story_report=self.build_story_report(project_id),
            log_summary=self.get_project_log_summary(project_id),
            log_connector=self._log_connectors.get(project_id),
            metric_summary=self.get_project_metric_summary(project_id),
            active_runs=[run for run in self.list_runs(project_id) if run.status != "resolved"],
            recent_events=self.list_project_events(project_id, limit=25),
        )

    def complete_predeploy_validation(self, project_id: str, story_ids: list[str]) -> PredeployValidationResult:
        guardian = self._update_agent_activity(
            project_id,
            AgentRole.TEST_ENV_GUARDIAN,
            success=all(
                self.get_story(story_id).status == StoryStatus.COMPLETED for story_id in story_ids if story_id in self._stories
            ),
            note=f"Completed predeploy validation for {len(story_ids)} stor{'y' if len(story_ids) == 1 else 'ies'}.",
        )
        stories = [self.get_story(story_id) for story_id in story_ids if story_id in self._stories]
        report = build_story_report(project_id, stories)
        release_ready = report.total_stories > 0 and report.failed_stories == 0 and report.blocked_stories == 0 and report.pending_stories == 0
        result = PredeployValidationResult(
            project_id=project_id,
            guardian_agent_id=guardian.agent_id,
            guardian_maturity=guardian.maturity,
            total_stories=report.total_stories,
            completed_stories=report.completed_stories,
            failed_stories=report.failed_stories,
            blocked_stories=report.blocked_stories,
            pending_stories=report.pending_stories,
            release_ready=release_ready,
            summary=(
                "Predeploy validation passed. All tracked stories are complete and the release can move forward."
                if release_ready
                else "Predeploy validation blocked. One or more stories are failed, blocked, or still pending."
            ),
            executed_story_ids=story_ids,
            stories=stories,
        )
        open_incident_count = sum(run.status != "resolved" for run in self.list_runs(project_id))
        latest_checks = self.list_validation_snapshots(project_id)
        latest_check_status = latest_checks[-1].status if latest_checks else None
        self._guardian_decisions.setdefault(project_id, []).append(
            GuardianDecisionRecord(
                validation_id=uuid4().hex,
                project_id=project_id,
                guardian_agent_id=guardian.agent_id,
                guardian_maturity=guardian.maturity,
                started_at=result.started_at,
                completed_at=result.completed_at,
                story_count=report.total_stories,
                completed_stories=report.completed_stories,
                failed_stories=report.failed_stories,
                blocked_stories=report.blocked_stories,
                pending_stories=report.pending_stories,
                release_ready=release_ready,
                open_incident_count=open_incident_count,
                latest_check_status=latest_check_status,
                summary=result.summary,
                decision_label="ready" if release_ready else "blocked",
                executed_story_ids=story_ids,
            )
        )
        self._record_event(
            project_id,
            event_type="predeploy_validation",
            title="Predeploy validation completed",
            message=result.summary,
            severity="info" if release_ready else "warning",
            source="testing",
            metadata={
                "release_ready": release_ready,
                "completed_stories": report.completed_stories,
                "failed_stories": report.failed_stories,
                "blocked_stories": report.blocked_stories,
                "pending_stories": report.pending_stories,
            },
            persist=False,
        )
        self._record_agent_handoff(
            project_id,
            from_role=AgentRole.TEST_ENV_GUARDIAN,
            to_role=AgentRole.OVERSIGHT,
            handoff_type="predeploy_review",
            summary="Test Environment Guardian sent release-readiness results to Oversight.",
            metadata={"release_ready": release_ready, "story_count": len(story_ids)},
            persist=False,
        )
        self._record_agent_message(
            project_id,
            sender_role=AgentRole.TEST_ENV_GUARDIAN,
            recipient_role=AgentRole.OVERSIGHT,
            message_type="predeploy_note",
            content=(
                f"Predeploy validation completed for {len(story_ids)} stor"
                f"{'y' if len(story_ids) == 1 else 'ies'}. "
                f"Release ready: {'yes' if release_ready else 'no'}."
            ),
            metadata={"release_ready": release_ready},
            persist=False,
        )
        self._save()
        return result

    def get_project(self, project_id: str) -> ProjectConfig:
        try:
            project = self._projects[project_id]
        except KeyError as exc:
            raise KeyError(f"Unknown project_id: {project_id}") from exc
        normalized = self._ensure_project_endpoint_defaults(project)
        self._projects[project_id] = normalized
        return normalized

    def list_project_endpoints(self, project_id: str) -> list[ProjectEndpoint]:
        project = self.get_project(project_id)
        return list(project.endpoints)

    def set_project_endpoints(self, project_id: str, request: ProjectEndpointBatchUpdateRequest) -> ProjectConfig:
        project = self.get_project(project_id)
        endpoints = self._build_project_endpoints(
            request_endpoints=request.endpoints,
            base_url=None,
            healthcheck_path=self._normalize_healthcheck_path(project.healthcheck_path),
        )
        if not endpoints:
            raise ValueError("At least one valid endpoint is required.")

        updated_project = project.model_copy(
            update={
                "endpoints": endpoints,
                "base_url": endpoints[0].base_url,
                "healthcheck_path": endpoints[0].healthcheck_path,
            }
        )
        updated_project = self._ensure_project_endpoint_defaults(updated_project)
        self._projects[project_id] = updated_project
        self._write_project(updated_project)
        self._record_event(
            project_id,
            event_type="project_endpoints_updated",
            title="Project endpoints updated",
            message=f"{len(updated_project.endpoints)} endpoint(s) configured for {updated_project.name}.",
            severity="info",
            source="project",
            metadata={
                "endpoint_count": len(updated_project.endpoints),
                "endpoint_ids": [endpoint.endpoint_id for endpoint in updated_project.endpoints],
            },
            persist=False,
        )
        self._save()
        return updated_project

    def set_monitor(self, project_id: str, request: WebsiteMonitorUpdateRequest) -> WebsiteMonitorConfig:
        project = self.get_project(project_id)
        try:
            endpoint = self.resolve_project_endpoint(
                project_id,
                endpoint_id=request.endpoint_id,
                preferred_surface=None,
            ) if request.endpoint_id else None
        except KeyError as exc:
            raise ValueError(str(exc)) from exc
        fallback_endpoint = endpoint or self.resolve_project_endpoint(project_id)
        selected_base_url = self._normalize_base_url(request.base_url) or (
            fallback_endpoint.base_url if fallback_endpoint else (project.base_url or "")
        )
        selected_health_path = self._normalize_healthcheck_path(
            request.healthcheck_path,
            fallback=(fallback_endpoint.healthcheck_path if fallback_endpoint else project.healthcheck_path),
        )
        monitor = WebsiteMonitorConfig(
            project_id=project_id,
            endpoint_id=(endpoint.endpoint_id if endpoint else (fallback_endpoint.endpoint_id if fallback_endpoint else None)),
            base_url=selected_base_url,
            healthcheck_path=selected_health_path,
            expected_status=request.expected_status,
            timeout_seconds=request.timeout_seconds,
            enabled=request.enabled,
            headers=request.headers,
        )
        self._monitors[project_id] = monitor
        self._write_monitor(monitor)
        self._record_event(
            project_id,
            event_type="monitor_configured",
            title="Monitor configured",
            message=f"Health path {monitor.healthcheck_path} is now monitored for {project.name}.",
            severity="info",
            source="monitor",
            persist=False,
        )
        self._save()
        return monitor

    def get_monitor(self, project_id: str) -> WebsiteMonitorConfig:
        try:
            return self._monitors[project_id]
        except KeyError as exc:
            raise KeyError(f"No website monitor configured for project_id: {project_id}") from exc

    def list_monitors(self) -> list[WebsiteMonitorConfig]:
        return list(self._monitors.values())

    def set_monitor_trigger(self, project_id: str, trigger: MonitorIncidentTrigger) -> MonitorIncidentTrigger:
        self.get_project(project_id)
        self._monitor_triggers[project_id] = trigger
        self._write_monitor_trigger(project_id, trigger)
        self._record_event(
            project_id,
            event_type="incident_trigger_updated",
            title="Auto incident trigger updated",
            message=f"Auto incident creation is {'enabled' if trigger.enabled and trigger.auto_create_run else 'disabled'}.",
            severity="info",
            source="monitor",
            metadata={"enabled": trigger.enabled, "auto_create_run": trigger.auto_create_run},
            persist=False,
        )
        self._save()
        return trigger

    def get_monitor_trigger(self, project_id: str) -> MonitorIncidentTrigger:
        return self._monitor_triggers.get(project_id, MonitorIncidentTrigger())

    def set_health_snapshot(self, snapshot: WebsiteHealthSnapshot) -> WebsiteHealthSnapshot:
        self._health_snapshots[snapshot.project_id] = snapshot
        self._write_health_snapshot(snapshot)
        self._record_event(
            snapshot.project_id,
            event_type="health_check",
            title=f"Health check {snapshot.status}",
            message=snapshot.error_message or snapshot.target_url,
            severity="error" if snapshot.status in {"unhealthy", "unreachable"} else "info",
            source="health",
            metadata={"status_code": snapshot.status_code, "response_time_ms": snapshot.response_time_ms},
            persist=False,
        )
        self._save()
        return snapshot

    def get_health_snapshot(self, project_id: str) -> WebsiteHealthSnapshot:
        try:
            return self._health_snapshots[project_id]
        except KeyError as exc:
            raise KeyError(f"No health snapshot available for project_id: {project_id}") from exc

    def add_validation_snapshot(self, snapshot: ProjectValidationSnapshot) -> ProjectValidationSnapshot:
        snapshots = self._validation_snapshots.setdefault(snapshot.project_id, [])
        snapshots.append(snapshot)
        self._write_validation_snapshot(snapshot)
        log_summary = self.get_project_log_summary(snapshot.project_id)
        metric_summary = self.get_project_metric_summary(snapshot.project_id)
        self._observability_records.setdefault(snapshot.project_id, []).append(
            ObservabilityTrainingRecord(
                record_id=uuid4().hex,
                project_id=snapshot.project_id,
                check_type=snapshot.check_type,
                label=snapshot.label,
                target_url=snapshot.target_url,
                status=snapshot.status,
                status_code=snapshot.status_code,
                response_time_ms=snapshot.response_time_ms,
                error_message=snapshot.error_message,
                log_error_entries=log_summary.error_entries,
                log_warning_entries=log_summary.warning_entries,
                top_signals=log_summary.top_signals[:5],
                degraded_metrics=metric_summary.degraded_metrics[:5],
                active_incident_count=sum(run.status != "resolved" for run in self.list_runs(snapshot.project_id)),
            )
        )
        self._record_event(
            snapshot.project_id,
            event_type=f"{snapshot.check_type}_check",
            title=f"{snapshot.check_type.capitalize()} check {snapshot.status}",
            message=snapshot.error_message or snapshot.label,
            severity="error" if snapshot.status in {"unhealthy", "unreachable"} else "info",
            source=snapshot.check_type,
            metadata={
                "target_url": snapshot.target_url,
                "status_code": snapshot.status_code,
                "response_time_ms": snapshot.response_time_ms,
            },
            persist=False,
        )
        self._save()
        return snapshot

    def list_validation_snapshots(self, project_id: str) -> list[ProjectValidationSnapshot]:
        return list(self._validation_snapshots.get(project_id, []))

    def create_session(
        self,
        task_id: str = "easy",
        max_steps: int | None = None,
        project: ProjectConfig | None = None,
        persist: bool = True,
        source: str = "manual",
        trigger_reason: str | None = None,
    ) -> tuple[SessionInfo, IncidentRun, ProductionIncidentEnv]:
        session_id = uuid4().hex
        session = SessionInfo(session_id=session_id, task_id=task_id, project=project)
        run = IncidentRun(
            run_id=uuid4().hex,
            session_id=session_id,
            task_id=task_id,
            project=project,
            source=source,
            trigger_reason=trigger_reason,
        )
        environment = ProductionIncidentEnv(task_id=task_id, max_steps=max_steps)
        self._sessions[session_id] = session
        self._environments[session_id] = environment
        self._runs[session_id] = run
        self._write_run(run)
        if persist:
            self._save()
        return session, run, environment

    def get_session(self, session_id: str) -> SessionInfo:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown session_id: {session_id}") from exc

    def get_environment(self, session_id: str) -> ProductionIncidentEnv:
        try:
            return self._environments[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown session_id: {session_id}") from exc

    def get_run(self, session_id: str) -> IncidentRun:
        try:
            return self._runs[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown session_id: {session_id}") from exc

    def list_runs(self, project_id: str | None = None) -> list[IncidentRun]:
        runs = list(self._runs.values())
        if project_id is not None:
            runs = [run for run in runs if run.project and run.project.project_id == project_id]
        return sorted(runs, key=lambda run: run.updated_at, reverse=True)

    def get_run_by_id(self, run_id: str) -> IncidentRun:
        for run in self._runs.values():
            if run.run_id == run_id:
                return run
        raise KeyError(f"Unknown run_id: {run_id}")

    def touch(self, session_id: str) -> SessionInfo:
        session = self.get_session(session_id)
        now = datetime.now(timezone.utc)
        session.updated_at = now
        self._sessions[session_id] = session
        run = self.get_run(session_id)
        run.updated_at = now
        self._runs[session_id] = run
        self._write_run(run)
        self._save()
        return session

    def record_step(
        self,
        session_id: str,
        reward: float,
        observation,
        done: bool,
    ) -> IncidentRun:
        run = self.get_run(session_id)
        run.reward_history.append(reward)
        run.last_observation = observation
        run.status = observation.current_status if done else "investigating"
        run.updated_at = datetime.now(timezone.utc)
        self._runs[session_id] = run
        self._write_run(run)
        if run.project:
            self._record_event(
                run.project.project_id,
                event_type="incident_step",
                title=f"Incident action {observation.last_action or 'updated'}",
                message=observation.last_action_error or observation.incident_summary,
                severity="error" if observation.last_action_error else "info",
                source="incident",
                related_run_id=run.run_id,
                related_session_id=session_id,
                metadata={"reward": reward, "done": done, "status": run.status},
                persist=False,
            )
        self._save()
        return run

    def create_monitor_incident(
        self,
        project_id: str,
        trigger_reason: str,
        signal_snapshot: WebsiteHealthSnapshot | ProjectValidationSnapshot,
    ) -> tuple[SessionInfo, IncidentRun, ProductionIncidentEnv]:
        project = self.get_project(project_id)
        trigger = self.get_monitor_trigger(project_id)
        session, run, environment = self.create_session(
            task_id=trigger.failure_task_id,
            project=project,
            source="monitor",
            trigger_reason=trigger_reason,
        )
        environment.prepare_external_incident(
            project_name=project.name,
            trigger_reason=trigger_reason,
            severity=trigger.severity,
            repository_url=project.repository_url,
            base_url=project.base_url,
        )
        observation = environment.attach_external_signal(
            project_name=project.name,
            target_url=signal_snapshot.target_url,
            status=signal_snapshot.status,
            check_type=signal_snapshot.check_type,
            label=getattr(signal_snapshot, "label", None),
            status_code=signal_snapshot.status_code,
            response_time_ms=signal_snapshot.response_time_ms,
            error_message=signal_snapshot.error_message,
            response_excerpt=signal_snapshot.response_excerpt,
        )
        run.last_observation = observation
        run.status = observation.current_status
        run.source_check_type = signal_snapshot.check_type
        run.source_target_url = signal_snapshot.target_url
        run.source_label = getattr(signal_snapshot, "label", None)
        self._runs[session.session_id] = run
        self._write_run(run)
        self._record_event(
            project_id,
            event_type="incident_opened",
            title="Monitor incident opened",
            message=trigger_reason,
            severity="error",
            source="incident",
            related_run_id=run.run_id,
            related_session_id=session.session_id,
            metadata={"check_type": signal_snapshot.check_type, "target_url": signal_snapshot.target_url},
            persist=False,
        )
        self._save()
        return session, run, environment

    def create_story_incident(
        self,
        project_id: str,
        story_title: str,
        trigger_reason: str,
        signal_snapshot: ProjectValidationSnapshot,
    ) -> tuple[SessionInfo, IncidentRun, ProductionIncidentEnv]:
        project = self.get_project(project_id)
        trigger = self.get_monitor_trigger(project_id)
        session, run, environment = self.create_session(
            task_id=trigger.failure_task_id,
            project=project,
            source="story",
            trigger_reason=trigger_reason,
        )
        environment.prepare_external_incident(
            project_name=project.name,
            trigger_reason=f"User story failed: {story_title}. {trigger_reason}",
            severity=trigger.severity,
            repository_url=project.repository_url,
            base_url=project.base_url,
        )
        observation = environment.attach_external_signal(
            project_name=project.name,
            target_url=signal_snapshot.target_url,
            status=signal_snapshot.status,
            check_type=signal_snapshot.check_type,
            label=signal_snapshot.label or story_title,
            status_code=signal_snapshot.status_code,
            response_time_ms=signal_snapshot.response_time_ms,
            error_message=signal_snapshot.error_message,
            response_excerpt=signal_snapshot.response_excerpt,
        )
        run.last_observation = observation
        run.status = observation.current_status
        run.source_check_type = signal_snapshot.check_type
        run.source_target_url = signal_snapshot.target_url
        run.source_label = signal_snapshot.label or story_title
        self._runs[session.session_id] = run
        self._write_run(run)
        self._record_event(
            project_id,
            event_type="incident_opened_from_story",
            title="Story incident opened",
            message=f"{story_title}: {trigger_reason}",
            severity="error",
            source="incident",
            related_run_id=run.run_id,
            related_session_id=session.session_id,
            metadata={"check_type": signal_snapshot.check_type, "target_url": signal_snapshot.target_url},
            persist=False,
        )
        self._save()
        return session, run, environment

    def resolve_recovered_monitor_runs(
        self,
        project_id: str,
        signal_snapshot: WebsiteHealthSnapshot | ProjectValidationSnapshot,
    ) -> list[IncidentRun]:
        resolved_runs: list[IncidentRun] = []
        project = self.get_project(project_id)
        for session_id, run in self._runs.items():
            if not run.project or run.project.project_id != project_id:
                continue
            if run.source != "monitor":
                continue
            if run.status == "resolved":
                continue
            if run.source_check_type != signal_snapshot.check_type:
                continue
            if run.source_target_url != signal_snapshot.target_url:
                continue

            environment = self._environments[session_id]
            observation = environment.mark_recovered_from_signal(
                project_name=project.name,
                target_url=signal_snapshot.target_url,
                check_type=signal_snapshot.check_type,
                label=getattr(signal_snapshot, "label", None),
                status_code=signal_snapshot.status_code,
                response_time_ms=signal_snapshot.response_time_ms,
            )
            run.last_observation = observation
            run.status = observation.current_status
            run.updated_at = datetime.now(timezone.utc)
            self._runs[session_id] = run
            self._write_run(run)
            resolved_runs.append(run)
            self._record_event(
                project_id,
                event_type="incident_resolved",
                title="Incident auto-resolved",
                message=f"{signal_snapshot.check_type.capitalize()} recovered for {signal_snapshot.target_url}.",
                severity="info",
                source="incident",
                related_run_id=run.run_id,
                related_session_id=session_id,
                metadata={"check_type": signal_snapshot.check_type, "target_url": signal_snapshot.target_url},
                persist=False,
            )

        if resolved_runs:
            self._save()
        return resolved_runs
