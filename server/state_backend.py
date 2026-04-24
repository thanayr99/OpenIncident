from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonStateBackend:
    def __init__(self, store_path: str | Path) -> None:
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> dict[str, Any]:
        if not self.store_path.exists():
            return {}
        return json.loads(self.store_path.read_text(encoding="utf-8"))

    def save_state(self, payload: dict[str, Any]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def health(self) -> dict[str, Any]:
        return {
            "engine": "json",
            "status": "ok",
            "path": str(self.store_path.resolve()),
            "updated_at": _utc_now_iso(),
        }

    def load_application_state(self) -> dict[str, Any]:
        return self.load_state()

    def upsert_auth_account(self, payload: dict[str, Any]) -> None:
        return

    def replace_auth_tokens(self, tokens: dict[str, str]) -> None:
        return

    def remove_auth_token(self, token: str) -> None:
        return

    def upsert_project(self, payload: dict[str, Any]) -> None:
        return

    def upsert_story(self, payload: dict[str, Any]) -> None:
        return

    def upsert_run(self, payload: dict[str, Any]) -> None:
        return

    def append_project_logs(self, project_id: str, entries: list[dict[str, Any]]) -> None:
        return

    def append_project_metrics(self, project_id: str, entries: list[dict[str, Any]]) -> None:
        return

    def append_project_event(self, payload: dict[str, Any]) -> None:
        return


class SqlAlchemyStateBackend:
    _MIGRATIONS = (
        ("001_app_state", "Create app_state namespace table"),
        ("002_normalized_core_tables", "Create normalized core entity tables"),
        ("003_operational_tables", "Create monitor, validation, and test environment tables"),
    )
    _NORMALIZED_TABLES = (
        "auth_accounts",
        "auth_tokens",
        "projects",
        "stories",
        "runs",
        "project_logs",
        "project_metrics",
        "project_events",
        "website_monitors",
        "monitor_triggers",
        "health_snapshots",
        "validation_snapshots",
        "test_environment_configs",
        "test_environment_runs",
    )
    _TABLE_ORDER_COLUMNS = {
        "app_state": "updated_at",
        "auth_accounts": "created_at",
        "auth_tokens": "issued_at",
        "projects": "created_at",
        "stories": "updated_at",
        "runs": "updated_at",
        "project_logs": "timestamp",
        "project_metrics": "timestamp",
        "project_events": "timestamp",
        "website_monitors": "updated_at",
        "monitor_triggers": "updated_at",
        "health_snapshots": "checked_at",
        "validation_snapshots": "checked_at",
        "test_environment_configs": "updated_at",
        "test_environment_runs": "completed_at",
    }

    def __init__(self, database_url: str, legacy_json_path: str | Path | None = None) -> None:
        self.database_url = database_url
        self.db_path = Path(database_url.replace("sqlite:///", "", 1)) if database_url.startswith("sqlite:///") else None
        if self.db_path is not None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.legacy_json_path = Path(legacy_json_path) if legacy_json_path else None
        self.engine: Engine = create_engine(
            self.database_url,
            future=True,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        self._initialize()

    def _initialize(self) -> None:
        with self.engine.begin() as connection:
            self._create_migration_table(connection)
            self._apply_migrations(connection)
        self._import_legacy_json_if_needed()

    def _create_migration_table(self, connection) -> None:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
        )

    def _has_migration(self, connection, version: str) -> bool:
        row = connection.execute(
            text("SELECT version FROM schema_migrations WHERE version = :version"),
            {"version": version},
        ).mappings().first()
        return row is not None

    def _mark_migration(self, connection, version: str, description: str) -> None:
        connection.execute(
            text(
                """
                INSERT INTO schema_migrations(version, description, applied_at)
                VALUES(:version, :description, :applied_at)
                ON CONFLICT(version) DO NOTHING
                """
            ),
            {
                "version": version,
                "description": description,
                "applied_at": _utc_now_iso(),
            },
        )

    def _apply_migrations(self, connection) -> None:
        for version, description in self._MIGRATIONS:
            if self._has_migration(connection, version):
                continue
            if version == "001_app_state":
                connection.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS app_state (
                            namespace TEXT PRIMARY KEY,
                            payload TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        )
                        """
                    )
                )
            elif version == "002_normalized_core_tables":
                self._create_normalized_tables(connection)
            elif version == "003_operational_tables":
                self._create_operational_tables(connection)
            self._mark_migration(connection, version, description)

    def _create_normalized_tables(self, connection) -> None:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS auth_accounts (
                    account_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    team TEXT,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    token TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    issued_at TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_url TEXT,
                    repository_url TEXT,
                    healthcheck_path TEXT,
                    owner_id TEXT,
                    created_at TEXT NOT NULL,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS stories (
                    story_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    primary_domain TEXT,
                    assigned_agent TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    project_id TEXT,
                    task_id TEXT NOT NULL,
                    source TEXT,
                    status TEXT NOT NULL,
                    trigger_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS project_logs (
                    log_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    source TEXT,
                    message TEXT NOT NULL,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS project_metrics (
                    metric_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value DOUBLE PRECISION NOT NULL,
                    unit TEXT,
                    source TEXT,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS project_events (
                    event_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    source TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )

    def _create_operational_tables(self, connection) -> None:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS website_monitors (
                    project_id TEXT PRIMARY KEY,
                    base_url TEXT NOT NULL,
                    healthcheck_path TEXT NOT NULL,
                    expected_status INTEGER NOT NULL,
                    timeout_seconds DOUBLE PRECISION NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    updated_at TEXT NOT NULL,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS monitor_triggers (
                    project_id TEXT PRIMARY KEY,
                    enabled BOOLEAN NOT NULL,
                    failure_task_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    auto_create_run BOOLEAN NOT NULL,
                    updated_at TEXT NOT NULL,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS health_snapshots (
                    project_id TEXT PRIMARY KEY,
                    checked_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    check_type TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    status_code INTEGER,
                    response_time_ms DOUBLE PRECISION,
                    error_message TEXT,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS validation_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    check_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    status_code INTEGER,
                    response_time_ms DOUBLE PRECISION,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_environment_configs (
                    project_id TEXT PRIMARY KEY,
                    repository_url TEXT NOT NULL,
                    branch TEXT,
                    test_command TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    shell TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_environment_runs (
                    run_key TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    repository_url TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    raw_payload TEXT NOT NULL
                )
                """
            )
        )

    def _is_empty(self) -> bool:
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT COUNT(*) AS count FROM app_state")).mappings().first()
        return bool(row and row["count"] == 0)

    def _import_legacy_json_if_needed(self) -> None:
        if not self.legacy_json_path or not self.legacy_json_path.exists() or not self._is_empty():
            return
        payload = json.loads(self.legacy_json_path.read_text(encoding="utf-8"))
        self.save_state(payload)

    def load_state(self) -> dict[str, Any]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("SELECT namespace, payload FROM app_state")).mappings().all()
        return {row["namespace"]: json.loads(row["payload"]) for row in rows}

    def load_application_state(self) -> dict[str, Any]:
        payload = self.load_state()

        with self.engine.connect() as connection:
            auth_account_rows = connection.execute(
                text("SELECT account_id, raw_payload FROM auth_accounts")
            ).mappings().all()
            if auth_account_rows:
                payload["auth_accounts"] = {
                    row["account_id"]: json.loads(row["raw_payload"])
                    for row in auth_account_rows
                }

            auth_token_rows = connection.execute(
                text("SELECT token, account_id FROM auth_tokens")
            ).mappings().all()
            if auth_token_rows:
                payload["auth_tokens"] = {
                    row["token"]: row["account_id"]
                    for row in auth_token_rows
                }

            project_rows = connection.execute(
                text("SELECT project_id, raw_payload FROM projects")
            ).mappings().all()
            if project_rows:
                payload["projects"] = {
                    row["project_id"]: json.loads(row["raw_payload"])
                    for row in project_rows
                }

            story_rows = connection.execute(
                text("SELECT story_id, raw_payload FROM stories")
            ).mappings().all()
            if story_rows:
                payload["stories"] = {
                    row["story_id"]: json.loads(row["raw_payload"])
                    for row in story_rows
                }

            run_rows = connection.execute(
                text("SELECT session_id, raw_payload FROM runs")
            ).mappings().all()
            if run_rows:
                payload["runs"] = {
                    row["session_id"]: json.loads(row["raw_payload"])
                    for row in run_rows
                }

            log_rows = connection.execute(
                text("SELECT project_id, raw_payload FROM project_logs ORDER BY timestamp ASC")
            ).mappings().all()
            if log_rows:
                logs_by_project: dict[str, list[dict[str, Any]]] = {}
                for row in log_rows:
                    logs_by_project.setdefault(row["project_id"], []).append(json.loads(row["raw_payload"]))
                payload["project_logs"] = logs_by_project

            metric_rows = connection.execute(
                text("SELECT project_id, raw_payload FROM project_metrics ORDER BY timestamp ASC")
            ).mappings().all()
            if metric_rows:
                metrics_by_project: dict[str, list[dict[str, Any]]] = {}
                for row in metric_rows:
                    metrics_by_project.setdefault(row["project_id"], []).append(json.loads(row["raw_payload"]))
                payload["project_metrics"] = metrics_by_project

            event_rows = connection.execute(
                text("SELECT project_id, raw_payload FROM project_events ORDER BY timestamp ASC")
            ).mappings().all()
            if event_rows:
                events_by_project: dict[str, list[dict[str, Any]]] = {}
                for row in event_rows:
                    events_by_project.setdefault(row["project_id"], []).append(json.loads(row["raw_payload"]))
                payload["project_events"] = events_by_project

            monitor_rows = connection.execute(
                text("SELECT project_id, raw_payload FROM website_monitors")
            ).mappings().all()
            if monitor_rows:
                payload["monitors"] = {
                    row["project_id"]: json.loads(row["raw_payload"])
                    for row in monitor_rows
                }

            trigger_rows = connection.execute(
                text("SELECT project_id, raw_payload FROM monitor_triggers")
            ).mappings().all()
            if trigger_rows:
                payload["monitor_triggers"] = {
                    row["project_id"]: json.loads(row["raw_payload"])
                    for row in trigger_rows
                }

            health_rows = connection.execute(
                text("SELECT project_id, raw_payload FROM health_snapshots")
            ).mappings().all()
            if health_rows:
                payload["health_snapshots"] = {
                    row["project_id"]: json.loads(row["raw_payload"])
                    for row in health_rows
                }

            validation_rows = connection.execute(
                text("SELECT project_id, raw_payload FROM validation_snapshots ORDER BY checked_at ASC")
            ).mappings().all()
            if validation_rows:
                snapshots_by_project: dict[str, list[dict[str, Any]]] = {}
                for row in validation_rows:
                    snapshots_by_project.setdefault(row["project_id"], []).append(json.loads(row["raw_payload"]))
                payload["validation_snapshots"] = snapshots_by_project

            test_env_config_rows = connection.execute(
                text("SELECT project_id, raw_payload FROM test_environment_configs")
            ).mappings().all()
            if test_env_config_rows:
                payload["test_env_configs"] = {
                    row["project_id"]: json.loads(row["raw_payload"])
                    for row in test_env_config_rows
                }

            test_env_run_rows = connection.execute(
                text("SELECT project_id, raw_payload FROM test_environment_runs ORDER BY completed_at ASC")
            ).mappings().all()
            if test_env_run_rows:
                runs_by_project: dict[str, list[dict[str, Any]]] = {}
                for row in test_env_run_rows:
                    runs_by_project.setdefault(row["project_id"], []).append(json.loads(row["raw_payload"]))
                payload["test_env_runs"] = runs_by_project

        return payload

    def save_state(self, payload: dict[str, Any]) -> None:
        timestamp = _utc_now_iso()
        with self.engine.begin() as connection:
            existing_rows = connection.execute(text("SELECT namespace FROM app_state")).mappings().all()
            existing_namespaces = {row["namespace"] for row in existing_rows}
            incoming_namespaces = set(payload.keys())

            for namespace, value in payload.items():
                connection.execute(
                    text(
                        """
                    INSERT INTO app_state(namespace, payload, updated_at)
                    VALUES(:namespace, :payload, :updated_at)
                    ON CONFLICT(namespace) DO UPDATE SET
                        payload = excluded.payload,
                        updated_at = excluded.updated_at
                    """
                    ),
                    {
                        "namespace": namespace,
                        "payload": json.dumps(value),
                        "updated_at": timestamp,
                    },
                )

            stale_namespaces = existing_namespaces - incoming_namespaces
            if stale_namespaces:
                connection.execute(
                    text("DELETE FROM app_state WHERE namespace IN :namespaces").bindparams(
                        bindparam("namespaces", expanding=True)
                    ),
                    {"namespaces": list(stale_namespaces)},
                )
            self._sync_normalized_tables(connection, payload, timestamp)

    def _replace_table_rows(self, connection, table_name: str, rows: list[dict[str, Any]]) -> None:
        connection.execute(text(f"DELETE FROM {table_name}"))
        if not rows:
            return
        columns = list(rows[0].keys())
        placeholders = ", ".join(f":{column}" for column in columns)
        column_list = ", ".join(columns)
        connection.execute(
            text(f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})"),
            rows,
        )

    def _dedupe_rows(self, rows: list[dict[str, Any]], key_field: str) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row.get(key_field, ""))
            deduped[key] = row
        return list(deduped.values())

    def _sync_normalized_tables(self, connection, payload: dict[str, Any], timestamp: str) -> None:
        auth_accounts = []
        for account_id, account in payload.get("auth_accounts", {}).items():
            auth_accounts.append(
                {
                    "account_id": account_id,
                    "name": account.get("name", ""),
                    "email": account.get("email", ""),
                    "team": account.get("team", ""),
                    "password_hash": account.get("password_hash", ""),
                    "created_at": account.get("created_at", timestamp),
                    "raw_payload": json.dumps(account),
                }
            )
        self._replace_table_rows(connection, "auth_accounts", auth_accounts)

        auth_tokens = []
        for token, account_id in payload.get("auth_tokens", {}).items():
            auth_tokens.append(
                {
                    "token": token,
                    "account_id": account_id,
                    "issued_at": timestamp,
                }
            )
        self._replace_table_rows(connection, "auth_tokens", auth_tokens)

        projects = []
        for project_id, project in payload.get("projects", {}).items():
            metadata = project.get("metadata", {}) or {}
            projects.append(
                {
                    "project_id": project_id,
                    "name": project.get("name", ""),
                    "base_url": project.get("base_url"),
                    "repository_url": project.get("repository_url"),
                    "healthcheck_path": project.get("healthcheck_path"),
                    "owner_id": metadata.get("owner_id"),
                    "created_at": timestamp,
                    "raw_payload": json.dumps(project),
                }
            )
        self._replace_table_rows(connection, "projects", projects)

        stories = []
        for story_id, story in payload.get("stories", {}).items():
            analysis = story.get("analysis") or {}
            stories.append(
                {
                    "story_id": story_id,
                    "project_id": story.get("project_id", ""),
                    "title": story.get("title", ""),
                    "status": story.get("status", "pending"),
                    "primary_domain": analysis.get("primary_domain"),
                    "assigned_agent": analysis.get("assigned_agent"),
                    "created_at": story.get("created_at", timestamp),
                    "updated_at": story.get("updated_at", timestamp),
                    "raw_payload": json.dumps(story),
                }
            )
        self._replace_table_rows(connection, "stories", stories)

        runs = []
        for _session_id, run in payload.get("runs", {}).items():
            project = run.get("project") or {}
            runs.append(
                {
                    "run_id": run.get("run_id", ""),
                    "session_id": run.get("session_id", ""),
                    "project_id": project.get("project_id"),
                    "task_id": run.get("task_id", ""),
                    "source": run.get("source"),
                    "status": run.get("status", "investigating"),
                    "trigger_reason": run.get("trigger_reason"),
                    "created_at": run.get("created_at", timestamp),
                    "updated_at": run.get("updated_at", timestamp),
                    "raw_payload": json.dumps(run),
                }
            )
        self._replace_table_rows(connection, "runs", runs)

        logs = []
        for project_id, entries in payload.get("project_logs", {}).items():
            for entry in entries:
                logs.append(
                    {
                        "log_id": entry.get("log_id", ""),
                        "project_id": project_id,
                        "timestamp": entry.get("timestamp", timestamp),
                        "level": entry.get("level", "INFO"),
                        "source": entry.get("source"),
                        "message": entry.get("message", ""),
                        "raw_payload": json.dumps(entry),
                    }
                )
        self._replace_table_rows(connection, "project_logs", logs)

        metrics = []
        for project_id, entries in payload.get("project_metrics", {}).items():
            for entry in entries:
                metrics.append(
                    {
                        "metric_id": entry.get("metric_id", ""),
                        "project_id": project_id,
                        "timestamp": entry.get("timestamp", timestamp),
                        "name": entry.get("name", ""),
                        "value": entry.get("value", 0.0),
                        "unit": entry.get("unit"),
                        "source": entry.get("source"),
                        "raw_payload": json.dumps(entry),
                    }
                )
        self._replace_table_rows(connection, "project_metrics", metrics)

        events = []
        for project_id, entries in payload.get("project_events", {}).items():
            for entry in entries:
                events.append(
                    {
                        "event_id": entry.get("event_id", ""),
                        "project_id": project_id,
                        "event_type": entry.get("event_type", ""),
                        "title": entry.get("title", ""),
                        "severity": entry.get("severity", "info"),
                        "source": entry.get("source", "system"),
                        "timestamp": entry.get("timestamp", timestamp),
                        "raw_payload": json.dumps(entry),
                    }
                )
        self._replace_table_rows(connection, "project_events", events)

        monitors = []
        for project_id, monitor in payload.get("monitors", {}).items():
            monitors.append(
                {
                    "project_id": project_id,
                    "base_url": monitor.get("base_url", ""),
                    "healthcheck_path": monitor.get("healthcheck_path", "/health"),
                    "expected_status": monitor.get("expected_status", 200),
                    "timeout_seconds": monitor.get("timeout_seconds", 10.0),
                    "enabled": monitor.get("enabled", True),
                    "updated_at": timestamp,
                    "raw_payload": json.dumps(monitor),
                }
            )
        self._replace_table_rows(connection, "website_monitors", monitors)

        triggers = []
        for project_id, trigger in payload.get("monitor_triggers", {}).items():
            triggers.append(
                {
                    "project_id": project_id,
                    "enabled": trigger.get("enabled", True),
                    "failure_task_id": trigger.get("failure_task_id", "easy"),
                    "severity": trigger.get("severity", "high"),
                    "auto_create_run": trigger.get("auto_create_run", True),
                    "updated_at": timestamp,
                    "raw_payload": json.dumps(trigger),
                }
            )
        self._replace_table_rows(connection, "monitor_triggers", triggers)

        health_snapshots = []
        for project_id, snapshot in payload.get("health_snapshots", {}).items():
            health_snapshots.append(
                {
                    "project_id": project_id,
                    "checked_at": snapshot.get("checked_at", timestamp),
                    "status": snapshot.get("status", "unknown"),
                    "check_type": snapshot.get("check_type", "health"),
                    "target_url": snapshot.get("target_url", ""),
                    "status_code": snapshot.get("status_code"),
                    "response_time_ms": snapshot.get("response_time_ms"),
                    "error_message": snapshot.get("error_message"),
                    "raw_payload": json.dumps(snapshot),
                }
            )
        self._replace_table_rows(connection, "health_snapshots", health_snapshots)

        validation_snapshots = []
        for project_id, entries in payload.get("validation_snapshots", {}).items():
            for entry in entries:
                snapshot_id = entry.get("project_id", project_id) + ":" + entry.get("checked_at", timestamp) + ":" + entry.get("label", "")
                validation_snapshots.append(
                    {
                        "snapshot_id": snapshot_id,
                        "project_id": project_id,
                        "checked_at": entry.get("checked_at", timestamp),
                        "check_type": entry.get("check_type", ""),
                        "label": entry.get("label", ""),
                        "target_url": entry.get("target_url", ""),
                        "status": entry.get("status", "unknown"),
                        "status_code": entry.get("status_code"),
                        "response_time_ms": entry.get("response_time_ms"),
                        "raw_payload": json.dumps(entry),
                    }
                )
        self._replace_table_rows(
            connection,
            "validation_snapshots",
            self._dedupe_rows(validation_snapshots, "snapshot_id"),
        )

        test_env_configs = []
        for project_id, config in payload.get("test_env_configs", {}).items():
            test_env_configs.append(
                {
                    "project_id": project_id,
                    "repository_url": config.get("repository_url", ""),
                    "branch": config.get("branch"),
                    "test_command": config.get("test_command", "pytest"),
                    "enabled": config.get("enabled", True),
                    "shell": config.get("shell", "powershell"),
                    "updated_at": config.get("updated_at", timestamp),
                    "raw_payload": json.dumps(config),
                }
            )
        self._replace_table_rows(connection, "test_environment_configs", test_env_configs)

        test_env_runs = []
        for project_id, entries in payload.get("test_env_runs", {}).items():
            for entry in entries:
                run_key = f"{project_id}:{entry.get('started_at', timestamp)}:{entry.get('workspace_path', '')}"
                test_env_runs.append(
                    {
                        "run_key": run_key,
                        "project_id": project_id,
                        "repository_url": entry.get("repository_url", ""),
                        "workspace_path": entry.get("workspace_path", ""),
                        "success": entry.get("success", False),
                        "started_at": entry.get("started_at", timestamp),
                        "completed_at": entry.get("completed_at", timestamp),
                        "raw_payload": json.dumps(entry),
                    }
                )
        self._replace_table_rows(
            connection,
            "test_environment_runs",
            self._dedupe_rows(test_env_runs, "run_key"),
        )

    def health(self) -> dict[str, Any]:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            row = connection.execute(text("SELECT COUNT(*) AS count FROM app_state")).mappings().first()
            count = row["count"] if row else 0
            normalized_counts = {
                table_name: connection.execute(text(f"SELECT COUNT(*) AS count FROM {table_name}")).mappings().first()["count"]
                for table_name in self._NORMALIZED_TABLES
            }
        return {
            "engine": self.engine.dialect.name,
            "status": "ok",
            "database_url": self.database_url,
            "path": str(self.db_path.resolve()) if self.db_path is not None else None,
            "namespaces": count,
            "normalized_counts": normalized_counts,
            "updated_at": _utc_now_iso(),
        }

    def get_database_overview(self) -> dict[str, Any]:
        health = self.health()
        return {
            "engine": health["engine"],
            "database_url": health["database_url"],
            "app_state_namespaces": health["namespaces"],
            "tables": [
                {"table_name": table_name, "row_count": row_count}
                for table_name, row_count in health.get("normalized_counts", {}).items()
            ],
        }

    def get_migration_status(self) -> dict[str, Any]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text("SELECT version, description, applied_at FROM schema_migrations ORDER BY version ASC")
            ).mappings().all()
        migrations = [dict(row) for row in rows]
        current_version = migrations[-1]["version"] if migrations else "none"
        return {
            "engine": self.engine.dialect.name,
            "current_version": current_version,
            "migrations": migrations,
        }

    def list_table_rows(self, table_name: str, limit: int = 50) -> list[dict[str, Any]]:
        allowed_tables = {"app_state", *self._NORMALIZED_TABLES}
        if table_name not in allowed_tables:
            raise KeyError(f"Unsupported table: {table_name}")

        order_column = self._TABLE_ORDER_COLUMNS.get(table_name)
        if order_column:
            sql = text(f"SELECT * FROM {table_name} ORDER BY {order_column} DESC LIMIT :limit")
        else:
            sql = text(f"SELECT * FROM {table_name} LIMIT :limit")
        with self.engine.connect() as connection:
            rows = connection.execute(sql, {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def upsert_auth_account(self, payload: dict[str, Any]) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO auth_accounts(account_id, name, email, team, password_hash, created_at, raw_payload)
                    VALUES(:account_id, :name, :email, :team, :password_hash, :created_at, :raw_payload)
                    ON CONFLICT(account_id) DO UPDATE SET
                        name = excluded.name,
                        email = excluded.email,
                        team = excluded.team,
                        password_hash = excluded.password_hash,
                        created_at = excluded.created_at,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "account_id": payload.get("account_id"),
                    "name": payload.get("name", ""),
                    "email": payload.get("email", ""),
                    "team": payload.get("team", ""),
                    "password_hash": payload.get("password_hash", ""),
                    "created_at": payload.get("created_at", _utc_now_iso()),
                    "raw_payload": json.dumps(payload),
                },
            )

    def replace_auth_tokens(self, tokens: dict[str, str]) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM auth_tokens"))
            if not tokens:
                return
            rows = [
                {"token": token, "account_id": account_id, "issued_at": _utc_now_iso()}
                for token, account_id in tokens.items()
            ]
            connection.execute(
                text("INSERT INTO auth_tokens(token, account_id, issued_at) VALUES(:token, :account_id, :issued_at)"),
                rows,
            )

    def remove_auth_token(self, token: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM auth_tokens WHERE token = :token"), {"token": token})

    def upsert_project(self, payload: dict[str, Any]) -> None:
        metadata = payload.get("metadata", {}) or {}
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO projects(project_id, name, base_url, repository_url, healthcheck_path, owner_id, created_at, raw_payload)
                    VALUES(:project_id, :name, :base_url, :repository_url, :healthcheck_path, :owner_id, :created_at, :raw_payload)
                    ON CONFLICT(project_id) DO UPDATE SET
                        name = excluded.name,
                        base_url = excluded.base_url,
                        repository_url = excluded.repository_url,
                        healthcheck_path = excluded.healthcheck_path,
                        owner_id = excluded.owner_id,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "project_id": payload.get("project_id"),
                    "name": payload.get("name", ""),
                    "base_url": payload.get("base_url"),
                    "repository_url": payload.get("repository_url"),
                    "healthcheck_path": payload.get("healthcheck_path"),
                    "owner_id": metadata.get("owner_id"),
                    "created_at": payload.get("created_at", _utc_now_iso()),
                    "raw_payload": json.dumps(payload),
                },
            )

    def upsert_story(self, payload: dict[str, Any]) -> None:
        analysis = payload.get("analysis") or {}
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO stories(story_id, project_id, title, status, primary_domain, assigned_agent, created_at, updated_at, raw_payload)
                    VALUES(:story_id, :project_id, :title, :status, :primary_domain, :assigned_agent, :created_at, :updated_at, :raw_payload)
                    ON CONFLICT(story_id) DO UPDATE SET
                        title = excluded.title,
                        status = excluded.status,
                        primary_domain = excluded.primary_domain,
                        assigned_agent = excluded.assigned_agent,
                        updated_at = excluded.updated_at,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "story_id": payload.get("story_id"),
                    "project_id": payload.get("project_id"),
                    "title": payload.get("title", ""),
                    "status": payload.get("status", "pending"),
                    "primary_domain": analysis.get("primary_domain"),
                    "assigned_agent": analysis.get("assigned_agent"),
                    "created_at": payload.get("created_at", _utc_now_iso()),
                    "updated_at": payload.get("updated_at", _utc_now_iso()),
                    "raw_payload": json.dumps(payload),
                },
            )

    def upsert_run(self, payload: dict[str, Any]) -> None:
        project = payload.get("project") or {}
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO runs(run_id, session_id, project_id, task_id, source, status, trigger_reason, created_at, updated_at, raw_payload)
                    VALUES(:run_id, :session_id, :project_id, :task_id, :source, :status, :trigger_reason, :created_at, :updated_at, :raw_payload)
                    ON CONFLICT(run_id) DO UPDATE SET
                        project_id = excluded.project_id,
                        source = excluded.source,
                        status = excluded.status,
                        trigger_reason = excluded.trigger_reason,
                        updated_at = excluded.updated_at,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "run_id": payload.get("run_id"),
                    "session_id": payload.get("session_id"),
                    "project_id": project.get("project_id"),
                    "task_id": payload.get("task_id", ""),
                    "source": payload.get("source"),
                    "status": payload.get("status", "investigating"),
                    "trigger_reason": payload.get("trigger_reason"),
                    "created_at": payload.get("created_at", _utc_now_iso()),
                    "updated_at": payload.get("updated_at", _utc_now_iso()),
                    "raw_payload": json.dumps(payload),
                },
            )

    def append_project_logs(self, project_id: str, entries: list[dict[str, Any]]) -> None:
        if not entries:
            return
        rows = [
            {
                "log_id": entry.get("log_id"),
                "project_id": project_id,
                "timestamp": entry.get("timestamp", _utc_now_iso()),
                "level": entry.get("level", "INFO"),
                "source": entry.get("source"),
                "message": entry.get("message", ""),
                "raw_payload": json.dumps(entry),
            }
            for entry in entries
        ]
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO project_logs(log_id, project_id, timestamp, level, source, message, raw_payload)
                    VALUES(:log_id, :project_id, :timestamp, :level, :source, :message, :raw_payload)
                    ON CONFLICT(log_id) DO UPDATE SET
                        timestamp = excluded.timestamp,
                        level = excluded.level,
                        source = excluded.source,
                        message = excluded.message,
                        raw_payload = excluded.raw_payload
                    """
                ),
                rows,
            )

    def append_project_metrics(self, project_id: str, entries: list[dict[str, Any]]) -> None:
        if not entries:
            return
        rows = [
            {
                "metric_id": entry.get("metric_id"),
                "project_id": project_id,
                "timestamp": entry.get("timestamp", _utc_now_iso()),
                "name": entry.get("name", ""),
                "value": entry.get("value", 0.0),
                "unit": entry.get("unit"),
                "source": entry.get("source"),
                "raw_payload": json.dumps(entry),
            }
            for entry in entries
        ]
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO project_metrics(metric_id, project_id, timestamp, name, value, unit, source, raw_payload)
                    VALUES(:metric_id, :project_id, :timestamp, :name, :value, :unit, :source, :raw_payload)
                    ON CONFLICT(metric_id) DO UPDATE SET
                        timestamp = excluded.timestamp,
                        name = excluded.name,
                        value = excluded.value,
                        unit = excluded.unit,
                        source = excluded.source,
                        raw_payload = excluded.raw_payload
                    """
                ),
                rows,
            )

    def append_project_event(self, payload: dict[str, Any]) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO project_events(event_id, project_id, event_type, title, severity, source, timestamp, raw_payload)
                    VALUES(:event_id, :project_id, :event_type, :title, :severity, :source, :timestamp, :raw_payload)
                    ON CONFLICT(event_id) DO UPDATE SET
                        event_type = excluded.event_type,
                        title = excluded.title,
                        severity = excluded.severity,
                        source = excluded.source,
                        timestamp = excluded.timestamp,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "event_id": payload.get("event_id"),
                    "project_id": payload.get("project_id"),
                    "event_type": payload.get("event_type", ""),
                    "title": payload.get("title", ""),
                    "severity": payload.get("severity", "info"),
                    "source": payload.get("source", "system"),
                    "timestamp": payload.get("timestamp", _utc_now_iso()),
                    "raw_payload": json.dumps(payload),
                },
            )

    def upsert_monitor(self, project_id: str, payload: dict[str, Any]) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO website_monitors(project_id, base_url, healthcheck_path, expected_status, timeout_seconds, enabled, updated_at, raw_payload)
                    VALUES(:project_id, :base_url, :healthcheck_path, :expected_status, :timeout_seconds, :enabled, :updated_at, :raw_payload)
                    ON CONFLICT(project_id) DO UPDATE SET
                        base_url = excluded.base_url,
                        healthcheck_path = excluded.healthcheck_path,
                        expected_status = excluded.expected_status,
                        timeout_seconds = excluded.timeout_seconds,
                        enabled = excluded.enabled,
                        updated_at = excluded.updated_at,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "project_id": project_id,
                    "base_url": payload.get("base_url", ""),
                    "healthcheck_path": payload.get("healthcheck_path", "/health"),
                    "expected_status": payload.get("expected_status", 200),
                    "timeout_seconds": payload.get("timeout_seconds", 10.0),
                    "enabled": payload.get("enabled", True),
                    "updated_at": _utc_now_iso(),
                    "raw_payload": json.dumps(payload),
                },
            )

    def upsert_monitor_trigger(self, project_id: str, payload: dict[str, Any]) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO monitor_triggers(project_id, enabled, failure_task_id, severity, auto_create_run, updated_at, raw_payload)
                    VALUES(:project_id, :enabled, :failure_task_id, :severity, :auto_create_run, :updated_at, :raw_payload)
                    ON CONFLICT(project_id) DO UPDATE SET
                        enabled = excluded.enabled,
                        failure_task_id = excluded.failure_task_id,
                        severity = excluded.severity,
                        auto_create_run = excluded.auto_create_run,
                        updated_at = excluded.updated_at,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "project_id": project_id,
                    "enabled": payload.get("enabled", True),
                    "failure_task_id": payload.get("failure_task_id", "easy"),
                    "severity": payload.get("severity", "high"),
                    "auto_create_run": payload.get("auto_create_run", True),
                    "updated_at": _utc_now_iso(),
                    "raw_payload": json.dumps(payload),
                },
            )

    def upsert_health_snapshot(self, payload: dict[str, Any]) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO health_snapshots(project_id, checked_at, status, check_type, target_url, status_code, response_time_ms, error_message, raw_payload)
                    VALUES(:project_id, :checked_at, :status, :check_type, :target_url, :status_code, :response_time_ms, :error_message, :raw_payload)
                    ON CONFLICT(project_id) DO UPDATE SET
                        checked_at = excluded.checked_at,
                        status = excluded.status,
                        check_type = excluded.check_type,
                        target_url = excluded.target_url,
                        status_code = excluded.status_code,
                        response_time_ms = excluded.response_time_ms,
                        error_message = excluded.error_message,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "project_id": payload.get("project_id"),
                    "checked_at": payload.get("checked_at", _utc_now_iso()),
                    "status": payload.get("status", "unknown"),
                    "check_type": payload.get("check_type", "health"),
                    "target_url": payload.get("target_url", ""),
                    "status_code": payload.get("status_code"),
                    "response_time_ms": payload.get("response_time_ms"),
                    "error_message": payload.get("error_message"),
                    "raw_payload": json.dumps(payload),
                },
            )

    def append_validation_snapshot(self, payload: dict[str, Any]) -> None:
        snapshot_id = f"{payload.get('project_id')}:{payload.get('checked_at', _utc_now_iso())}:{payload.get('label', '')}"
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO validation_snapshots(snapshot_id, project_id, checked_at, check_type, label, target_url, status, status_code, response_time_ms, raw_payload)
                    VALUES(:snapshot_id, :project_id, :checked_at, :check_type, :label, :target_url, :status, :status_code, :response_time_ms, :raw_payload)
                    ON CONFLICT(snapshot_id) DO UPDATE SET
                        check_type = excluded.check_type,
                        label = excluded.label,
                        target_url = excluded.target_url,
                        status = excluded.status,
                        status_code = excluded.status_code,
                        response_time_ms = excluded.response_time_ms,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "snapshot_id": snapshot_id,
                    "project_id": payload.get("project_id"),
                    "checked_at": payload.get("checked_at", _utc_now_iso()),
                    "check_type": payload.get("check_type", ""),
                    "label": payload.get("label", ""),
                    "target_url": payload.get("target_url", ""),
                    "status": payload.get("status", "unknown"),
                    "status_code": payload.get("status_code"),
                    "response_time_ms": payload.get("response_time_ms"),
                    "raw_payload": json.dumps(payload),
                },
            )

    def upsert_test_environment_config(self, project_id: str, payload: dict[str, Any]) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO test_environment_configs(project_id, repository_url, branch, test_command, enabled, shell, updated_at, raw_payload)
                    VALUES(:project_id, :repository_url, :branch, :test_command, :enabled, :shell, :updated_at, :raw_payload)
                    ON CONFLICT(project_id) DO UPDATE SET
                        repository_url = excluded.repository_url,
                        branch = excluded.branch,
                        test_command = excluded.test_command,
                        enabled = excluded.enabled,
                        shell = excluded.shell,
                        updated_at = excluded.updated_at,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "project_id": project_id,
                    "repository_url": payload.get("repository_url", ""),
                    "branch": payload.get("branch"),
                    "test_command": payload.get("test_command", "pytest"),
                    "enabled": payload.get("enabled", True),
                    "shell": payload.get("shell", "powershell"),
                    "updated_at": payload.get("updated_at", _utc_now_iso()),
                    "raw_payload": json.dumps(payload),
                },
            )

    def append_test_environment_run(self, project_id: str, payload: dict[str, Any]) -> None:
        run_key = f"{project_id}:{payload.get('started_at', _utc_now_iso())}:{payload.get('workspace_path', '')}"
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO test_environment_runs(run_key, project_id, repository_url, workspace_path, success, started_at, completed_at, raw_payload)
                    VALUES(:run_key, :project_id, :repository_url, :workspace_path, :success, :started_at, :completed_at, :raw_payload)
                    ON CONFLICT(run_key) DO UPDATE SET
                        repository_url = excluded.repository_url,
                        workspace_path = excluded.workspace_path,
                        success = excluded.success,
                        started_at = excluded.started_at,
                        completed_at = excluded.completed_at,
                        raw_payload = excluded.raw_payload
                    """
                ),
                {
                    "run_key": run_key,
                    "project_id": project_id,
                    "repository_url": payload.get("repository_url", ""),
                    "workspace_path": payload.get("workspace_path", ""),
                    "success": payload.get("success", False),
                    "started_at": payload.get("started_at", _utc_now_iso()),
                    "completed_at": payload.get("completed_at", _utc_now_iso()),
                    "raw_payload": json.dumps(payload),
                },
            )


def build_state_backend(
    *,
    store_path: str | Path | None = None,
    database_url: str | None = None,
) -> JsonStateBackend | SqlAlchemyStateBackend:
    if store_path is not None and Path(store_path).suffix.lower() == ".json":
        return JsonStateBackend(store_path)

    resolved_database_url = database_url or "sqlite:///data/openincident.db"
    legacy_json_path = store_path or "data/openincident_store.json"
    return SqlAlchemyStateBackend(resolved_database_url, legacy_json_path=legacy_json_path)
