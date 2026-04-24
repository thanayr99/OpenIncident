from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import requests


LOG_LINE_RE = re.compile(
    r"^\s*(?:\[(?P<level>[A-Za-z]+)\]\s*)?(?:(?P<source>[A-Za-z0-9_.-]+)\s*:\s*)?(?P<message>.+?)\s*$"
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_json_load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def safe_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def chunked(items: List[Any], size: int) -> Iterable[List[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def flatten_numeric_paths(data: Any, prefix: str = "") -> Dict[str, float]:
    flat: Dict[str, float] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flat.update(flatten_numeric_paths(value, path))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            path = f"{prefix}[{index}]"
            flat.update(flatten_numeric_paths(value, path))
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        flat[prefix] = float(data)
    return flat


def sanitize_metric_name(path: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", path).strip("_").lower()


def parse_metric_overrides(items: List[str]) -> Dict[str, float]:
    parsed: Dict[str, float] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --metric value '{item}'. Expected format NAME=VALUE.")
        name, raw_value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Invalid --metric value '{item}'. Metric name cannot be empty.")
        parsed[name] = float(raw_value)
    return parsed


def parse_log_line(line: str, default_source: str, default_level: str) -> Optional[dict[str, Any]]:
    stripped = line.strip()
    if not stripped:
        return None
    match = LOG_LINE_RE.match(stripped)
    if not match:
        return {
            "timestamp": utc_now_iso(),
            "level": default_level,
            "source": default_source,
            "message": stripped,
            "context": {},
        }
    level = (match.group("level") or default_level).upper()
    source = match.group("source") or default_source
    message = (match.group("message") or stripped).strip()
    return {
        "timestamp": utc_now_iso(),
        "level": level,
        "source": source,
        "message": message,
        "context": {},
    }


@dataclass
class BridgeConfig:
    api_base_url: str
    email: str
    password: str
    project_id: Optional[str]
    project_name: Optional[str]
    interval_seconds: float
    once: bool
    verify_tls: bool
    timeout_seconds: float
    log_files: List[Path]
    default_log_source: str
    default_log_level: str
    max_log_lines: int
    metrics_endpoint: Optional[str]
    metrics_paths: List[str]
    metrics_source: str
    metric_overrides: Dict[str, float]
    state_file: Path


class OpenIncidentApi:
    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.verify = config.verify_tls
        self.token: Optional[str] = None
        self.project_id: Optional[str] = config.project_id

    def _url(self, path: str) -> str:
        return urljoin(self.config.api_base_url.rstrip("/") + "/", path.lstrip("/"))

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            raise RuntimeError("Not authenticated yet")
        return {"Authorization": f"Bearer {self.token}"}

    def login(self) -> None:
        response = self.session.post(
            self._url("/auth/login"),
            json={"email": self.config.email, "password": self.config.password},
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("token")
        if not token:
            raise RuntimeError("Login response did not include token")
        self.token = token

    def resolve_project_id(self) -> str:
        if self.project_id:
            return self.project_id
        if not self.config.project_name:
            raise RuntimeError("Either --project-id or --project-name is required.")
        response = self.session.get(
            self._url("/projects"),
            headers=self._headers(),
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        projects = response.json()
        target = self.config.project_name.strip().lower()
        for project in projects:
            if str(project.get("name", "")).strip().lower() == target:
                self.project_id = str(project["project_id"])
                return self.project_id
        raise RuntimeError(f"Could not find project named '{self.config.project_name}'.")

    def ingest_logs(self, project_id: str, entries: List[dict[str, Any]]) -> int:
        if not entries:
            return 0
        total_imported = 0
        for batch in chunked(entries, 200):
            response = self.session.post(
                self._url(f"/projects/{project_id}/logs"),
                headers=self._headers(),
                json={"entries": batch},
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            total_imported += len(response.json())
        return total_imported

    def ingest_metrics(self, project_id: str, points: List[dict[str, Any]]) -> int:
        if not points:
            return 0
        total_imported = 0
        for batch in chunked(points, 200):
            response = self.session.post(
                self._url(f"/projects/{project_id}/metrics"),
                headers=self._headers(),
                json={"points": batch},
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            total_imported += len(response.json())
        return total_imported

    def fetch_metrics_payload(self) -> dict[str, Any]:
        if not self.config.metrics_endpoint:
            return {}
        response = self.session.get(self.config.metrics_endpoint, timeout=self.config.timeout_seconds)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("Metrics endpoint did not return JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Metrics endpoint JSON must be an object at top-level")
        return payload


class BridgeState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.payload = safe_json_load(path, default={"log_offsets": {}, "last_success_at": None})

    def get_log_offset(self, log_file: Path) -> int:
        return int(self.payload.get("log_offsets", {}).get(str(log_file), 0))

    def set_log_offset(self, log_file: Path, offset: int) -> None:
        log_offsets = dict(self.payload.get("log_offsets", {}))
        log_offsets[str(log_file)] = int(offset)
        self.payload["log_offsets"] = log_offsets

    def mark_success(self) -> None:
        self.payload["last_success_at"] = utc_now_iso()

    def save(self) -> None:
        safe_json_write(self.path, self.payload)


def collect_log_entries(config: BridgeConfig, state: BridgeState) -> List[dict[str, Any]]:
    entries: List[dict[str, Any]] = []
    for log_file in config.log_files:
        if not log_file.exists() or not log_file.is_file():
            continue

        current_size = log_file.stat().st_size
        previous_offset = state.get_log_offset(log_file)
        offset = previous_offset if 0 <= previous_offset <= current_size else 0
        with log_file.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            lines = handle.readlines()
            state.set_log_offset(log_file, handle.tell())

        if len(lines) > config.max_log_lines:
            lines = lines[-config.max_log_lines :]
        for line in lines:
            parsed = parse_log_line(line, config.default_log_source, config.default_log_level)
            if parsed is not None:
                parsed["context"] = {"ingest_file": str(log_file)}
                entries.append(parsed)
    return entries


def collect_metric_points(config: BridgeConfig, api: OpenIncidentApi) -> List[dict[str, Any]]:
    points: List[dict[str, Any]] = []
    payload = api.fetch_metrics_payload() if config.metrics_endpoint else {}
    flattened = flatten_numeric_paths(payload)

    selected: Dict[str, float]
    if config.metrics_paths:
        selected = {path: flattened[path] for path in config.metrics_paths if path in flattened}
    else:
        selected = flattened

    for path, value in selected.items():
        points.append(
            {
                "timestamp": utc_now_iso(),
                "name": sanitize_metric_name(path),
                "value": value,
                "source": config.metrics_source,
                "dimensions": {"path": path},
            }
        )

    for name, value in config.metric_overrides.items():
        points.append(
            {
                "timestamp": utc_now_iso(),
                "name": sanitize_metric_name(name),
                "value": value,
                "source": config.metrics_source,
                "dimensions": {"path": name, "mode": "override"},
            }
        )
    return points


def run_ingest_cycle(config: BridgeConfig, api: OpenIncidentApi, state: BridgeState, project_id: str) -> Tuple[int, int]:
    log_entries = collect_log_entries(config, state)
    metric_points = collect_metric_points(config, api)
    imported_logs = api.ingest_logs(project_id, log_entries)
    imported_metrics = api.ingest_metrics(project_id, metric_points)
    state.mark_success()
    state.save()
    return imported_logs, imported_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Push real-world logs and metrics into OpenIncident project datasets on a schedule."
    )
    parser.add_argument("--api-base-url", default=None, help="OpenIncident API base URL.")
    parser.add_argument("--email", default=None, help="OpenIncident account email.")
    parser.add_argument("--password", default=None, help="OpenIncident account password.")
    parser.add_argument("--project-id", default=None, help="Target project id.")
    parser.add_argument("--project-name", default=None, help="Target project name if id is not known.")
    parser.add_argument("--interval-seconds", type=float, default=60.0, help="Interval between ingestion cycles.")
    parser.add_argument("--once", action="store_true", help="Run a single ingestion cycle and exit.")
    parser.add_argument("--timeout-seconds", type=float, default=15.0, help="HTTP timeout for backend and sources.")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification.")

    parser.add_argument(
        "--log-file",
        action="append",
        default=[],
        help="Local log file to tail. Repeat for multiple files.",
    )
    parser.add_argument("--log-source", default="runtime", help="Default log source label.")
    parser.add_argument("--log-level", default="INFO", help="Default log level when parsing raw lines.")
    parser.add_argument("--max-log-lines", type=int, default=200, help="Max lines per file per cycle.")

    parser.add_argument("--metrics-endpoint", default=None, help="JSON endpoint with numeric metrics.")
    parser.add_argument(
        "--metrics-path",
        action="append",
        default=[],
        help="Specific JSON metric path to ingest. Repeat for multiple paths.",
    )
    parser.add_argument("--metrics-source", default="external", help="Metrics source label.")
    parser.add_argument(
        "--metric",
        action="append",
        default=[],
        help="Static metric override in NAME=VALUE format. Repeat for multiple values.",
    )

    parser.add_argument(
        "--state-file",
        default="artifacts/ingest/realtime_ingest_state.json",
        help="State file storing log offsets and last-success timestamp.",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> BridgeConfig:
    api_base_url = (args.api_base_url or os.getenv("OPENINCIDENT_API_BASE_URL") or "http://127.0.0.1:8000").strip()
    email = (args.email or os.getenv("OPENINCIDENT_EMAIL") or "").strip()
    password = args.password or os.getenv("OPENINCIDENT_PASSWORD") or ""
    project_id = (args.project_id or os.getenv("OPENINCIDENT_PROJECT_ID") or "").strip() or None
    project_name = (args.project_name or os.getenv("OPENINCIDENT_PROJECT_NAME") or "").strip() or None

    if not email:
        raise ValueError("Missing email. Provide --email or OPENINCIDENT_EMAIL.")
    if not password:
        if os.isatty(0):
            password = getpass.getpass("OpenIncident password: ").strip()
        if not password:
            raise ValueError("Missing password. Provide --password or OPENINCIDENT_PASSWORD.")

    log_files = [Path(path).expanduser().resolve() for path in args.log_file]
    metric_overrides = parse_metric_overrides(args.metric)
    if not log_files and not args.metrics_endpoint and not metric_overrides:
        raise ValueError(
            "Nothing to ingest: add at least one --log-file, a --metrics-endpoint, or one --metric NAME=VALUE."
        )
    if not project_id and not project_name:
        raise ValueError("Provide either --project-id or --project-name.")
    return BridgeConfig(
        api_base_url=api_base_url,
        email=email,
        password=password,
        project_id=project_id,
        project_name=project_name,
        interval_seconds=max(1.0, args.interval_seconds),
        once=bool(args.once),
        verify_tls=not bool(args.insecure),
        timeout_seconds=max(1.0, args.timeout_seconds),
        log_files=log_files,
        default_log_source=args.log_source.strip() or "runtime",
        default_log_level=(args.log_level.strip() or "INFO").upper(),
        max_log_lines=max(1, args.max_log_lines),
        metrics_endpoint=(args.metrics_endpoint.strip() if args.metrics_endpoint else None),
        metrics_paths=[item.strip() for item in args.metrics_path if item.strip()],
        metrics_source=args.metrics_source.strip() or "external",
        metric_overrides=metric_overrides,
        state_file=Path(args.state_file).expanduser().resolve(),
    )


def main() -> None:
    args = parse_args()
    config = build_config(args)

    api = OpenIncidentApi(config)
    state = BridgeState(config.state_file)

    print(f"[{utc_now_iso()}] Authenticating to {config.api_base_url} ...")
    api.login()
    project_id = api.resolve_project_id()
    print(f"[{utc_now_iso()}] Connected. Using project_id={project_id}")

    while True:
        cycle_started = time.time()
        try:
            logs_ingested, metrics_ingested = run_ingest_cycle(config, api, state, project_id)
            print(
                f"[{utc_now_iso()}] Ingested logs={logs_ingested}, metrics={metrics_ingested}, "
                f"state={config.state_file}"
            )
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            body = exc.response.text[:300] if exc.response is not None else str(exc)
            print(f"[{utc_now_iso()}] HTTP error status={status}: {body}")
        except Exception as exc:
            print(f"[{utc_now_iso()}] Ingestion cycle failed: {exc}")

        if config.once:
            break

        elapsed = time.time() - cycle_started
        sleep_for = max(0.0, config.interval_seconds - elapsed)
        if sleep_for > 0:
            time.sleep(sleep_for)


if __name__ == "__main__":
    main()
