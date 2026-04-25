from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

import requests

from models import (
    ProjectLogBatchRequest,
    ProjectLogConnectorConfig,
    ProjectLogConnectorPullResult,
    ProjectLogEntry,
    ProjectLogEntryInput,
    ProjectLogSummary,
)


ERROR_KEYWORDS = (
    "error",
    "exception",
    "traceback",
    "timeout",
    "failed",
    "503",
    "500",
    "database",
    "connection",
)


def create_log_entry(project_id: str, entry: ProjectLogEntryInput) -> ProjectLogEntry:
    return ProjectLogEntry(
        log_id=uuid4().hex,
        project_id=project_id,
        timestamp=entry.timestamp or datetime.now(timezone.utc),
        level=entry.level.upper(),
        source=entry.source,
        message=entry.message,
        context=entry.context,
    )


def create_log_entries(project_id: str, request: ProjectLogBatchRequest) -> list[ProjectLogEntry]:
    return [create_log_entry(project_id, entry) for entry in request.entries]


def _walk_path(payload: Any, path: str | None) -> Any:
    if not path:
        return payload
    current = payload
    for segment in [item for item in path.split(".") if item]:
        if isinstance(current, dict):
            current = current.get(segment)
        else:
            return None
    return current


def _normalize_text_logs(text: str, limit: int) -> list[ProjectLogEntryInput]:
    entries: list[ProjectLogEntryInput] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        level = "INFO"
        source = "remote"
        message = line
        if line.startswith("[") and "]" in line:
            prefix, rest = line.split("]", 1)
            level = prefix.strip("[] ").upper() or "INFO"
            message = rest.strip() or line
        if ":" in message:
            left, right = message.split(":", 1)
            if len(left) < 40:
                source = left.strip() or source
                message = right.strip() or message
        entries.append(ProjectLogEntryInput(level=level, source=source, message=message))
        if len(entries) >= limit:
            break
    return entries


def _normalize_json_logs(payload: Any, config: ProjectLogConnectorConfig, limit: int) -> list[ProjectLogEntryInput]:
    items = _walk_path(payload, config.entries_path)
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return []

    entries: list[ProjectLogEntryInput] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        message = str(item.get(config.message_field, "")).strip()
        if not message:
            continue
        level = str(item.get(config.level_field, "INFO")).upper()
        source = str(item.get(config.source_field, "remote"))
        timestamp_raw = item.get(config.timestamp_field)
        timestamp = None
        if isinstance(timestamp_raw, str) and timestamp_raw:
            try:
                timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
            except ValueError:
                timestamp = None
        entries.append(
            ProjectLogEntryInput(
                timestamp=timestamp,
                level=level,
                source=source,
                message=message,
                context=item,
            )
        )
    return entries


def _normalize_splunk_jsonl_logs(text: str, config: ProjectLogConnectorConfig, limit: int) -> list[ProjectLogEntryInput]:
    entries: list[ProjectLogEntryInput] = []
    for line in text.splitlines():
        raw_line = line.strip()
        if not raw_line:
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        event = payload.get("result") if isinstance(payload, dict) and isinstance(payload.get("result"), dict) else payload
        if not isinstance(event, dict):
            continue

        message = str(
            event.get(config.message_field)
            or event.get("_raw")
            or event.get("message")
            or ""
        ).strip()
        if not message:
            continue

        level_value = str(
            event.get(config.level_field)
            or event.get("level")
            or event.get("severity")
            or ""
        ).strip()
        if not level_value:
            lowered = message.lower()
            if any(token in lowered for token in ("error", "exception", "fail", "timeout")):
                level_value = "ERROR"
            elif any(token in lowered for token in ("warn", "deprecated")):
                level_value = "WARNING"
            else:
                level_value = "INFO"

        source = str(
            event.get(config.source_field)
            or event.get("source")
            or event.get("host")
            or "splunk"
        ).strip() or "splunk"

        timestamp_raw = event.get(config.timestamp_field) or event.get("_time")
        timestamp = None
        if isinstance(timestamp_raw, str) and timestamp_raw:
            try:
                timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
            except ValueError:
                try:
                    timestamp = datetime.fromtimestamp(float(timestamp_raw), tz=timezone.utc)
                except ValueError:
                    timestamp = None
        elif isinstance(timestamp_raw, (int, float)):
            timestamp = datetime.fromtimestamp(float(timestamp_raw), tz=timezone.utc)

        entries.append(
            ProjectLogEntryInput(
                timestamp=timestamp,
                level=level_value.upper(),
                source=source,
                message=message,
                context=event,
            )
        )
        if len(entries) >= limit:
            break

    return entries


def pull_logs_from_connector(project_id: str, config: ProjectLogConnectorConfig, limit: int = 100) -> tuple[list[ProjectLogEntryInput], ProjectLogConnectorPullResult]:
    method = config.method.upper()
    request_kwargs: dict[str, Any] = {
        "method": method,
        "url": config.url,
        "headers": config.headers,
        "params": config.query_params,
        "timeout": 15,
    }
    if method not in {"GET", "HEAD"} and config.payload:
        if config.payload_encoding.lower() == "form":
            request_kwargs["data"] = config.payload
        else:
            request_kwargs["json"] = config.payload

    try:
        response = requests.request(**request_kwargs)
        response.raise_for_status()
    except requests.RequestException as exc:
        return [], ProjectLogConnectorPullResult(
            project_id=project_id,
            success=False,
            summary="Failed to pull logs from the configured connector.",
            error_message=str(exc),
        )

    format_kind = config.format.lower()
    if format_kind == "json":
        try:
            payload = response.json()
        except ValueError as exc:
            return [], ProjectLogConnectorPullResult(
                project_id=project_id,
                success=False,
                summary="Configured JSON log connector returned invalid JSON.",
                error_message=str(exc),
            )
        inputs = _normalize_json_logs(payload, config, limit=limit)
    elif format_kind == "splunk_jsonl":
        inputs = _normalize_splunk_jsonl_logs(response.text, config, limit=limit)
    else:
        inputs = _normalize_text_logs(response.text, limit=limit)

    return inputs, ProjectLogConnectorPullResult(
        project_id=project_id,
        success=True,
        fetched_entries=len(inputs),
        imported_entries=len(inputs),
        summary=f"Pulled {len(inputs)} log entr{'y' if len(inputs) == 1 else 'ies'} from connector.",
        sample_messages=[entry.message for entry in inputs[:3]],
    )


def summarize_logs(project_id: str, entries: list[ProjectLogEntry]) -> ProjectLogSummary:
    total_entries = len(entries)
    error_entries = sum(entry.level.upper() == "ERROR" for entry in entries)
    warning_entries = sum(entry.level.upper() == "WARNING" for entry in entries)

    token_counter: Counter[str] = Counter()
    latest_errors: list[str] = []

    for entry in sorted(entries, key=lambda item: item.timestamp, reverse=True):
        message_lower = entry.message.lower()
        for keyword in ERROR_KEYWORDS:
            if keyword in message_lower:
                token_counter[keyword] += 1
        if entry.level.upper() in {"ERROR", "WARNING"} and len(latest_errors) < 5:
            latest_errors.append(f"[{entry.level.upper()}] {entry.message}")

    top_signals = [token for token, _ in token_counter.most_common(5)]
    return ProjectLogSummary(
        project_id=project_id,
        total_entries=total_entries,
        error_entries=error_entries,
        warning_entries=warning_entries,
        top_signals=top_signals,
        latest_errors=latest_errors,
    )
