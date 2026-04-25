from __future__ import annotations

import argparse
import getpass
import os
from typing import Any
from urllib.parse import urljoin

import requests


class OpenIncidentClient:
    def __init__(self, api_base_url: str, verify_tls: bool, timeout_seconds: float) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.verify = verify_tls
        self.token: str | None = None

    def _url(self, path: str) -> str:
        return urljoin(self.api_base_url + "/", path.lstrip("/"))

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("Client is not authenticated.")
        return {"Authorization": f"Bearer {self.token}"}

    def login(self, email: str, password: str) -> None:
        response = self.session.post(
            self._url("/auth/login"),
            json={"email": email, "password": password},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        token = response.json().get("token")
        if not token:
            raise RuntimeError("Login response did not include token.")
        self.token = token

    def resolve_project_id(self, project_id: str | None, project_name: str | None) -> str:
        if project_id:
            return project_id
        if not project_name:
            raise RuntimeError("Provide --project-id or --project-name.")
        response = self.session.get(
            self._url("/projects"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        target_name = project_name.strip().lower()
        for project in response.json():
            if str(project.get("name", "")).strip().lower() == target_name:
                return str(project.get("project_id"))
        raise RuntimeError(f"Project '{project_name}' not found.")

    def set_connector(self, project_id: str, connector_payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.put(
            self._url(f"/projects/{project_id}/logs/connector"),
            headers=self._headers(),
            json=connector_payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def pull_connector_logs(self, project_id: str, limit: int) -> dict[str, Any]:
        response = self.session.post(
            self._url(f"/projects/{project_id}/logs/connector/pull"),
            headers=self._headers(),
            json={"limit": limit},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configure OpenIncident Splunk log connector and optionally pull logs."
    )
    parser.add_argument("--api-base-url", default=None, help="OpenIncident API base URL.")
    parser.add_argument("--email", default=None, help="OpenIncident login email.")
    parser.add_argument("--password", default=None, help="OpenIncident login password.")
    parser.add_argument("--project-id", default=None, help="OpenIncident project id.")
    parser.add_argument("--project-name", default=None, help="OpenIncident project name if id is unknown.")
    parser.add_argument("--timeout-seconds", type=float, default=20.0, help="HTTP timeout.")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification.")

    parser.add_argument(
        "--splunk-url",
        default=None,
        help="Splunk jobs export endpoint, e.g. https://host:8089/services/search/jobs/export",
    )
    parser.add_argument(
        "--splunk-token",
        default=None,
        help="Splunk token for Authorization header. Can also use SPLUNK_TOKEN env var.",
    )
    parser.add_argument(
        "--search",
        default="search index=main | head 100",
        help="Splunk search query.",
    )
    parser.add_argument("--earliest-time", default="-15m", help="Splunk earliest_time.")
    parser.add_argument("--latest-time", default="now", help="Splunk latest_time.")
    parser.add_argument("--count", type=int, default=100, help="Splunk count.")

    parser.add_argument("--source-field", default="source", help="Source field in Splunk payload.")
    parser.add_argument("--level-field", default="level", help="Level field in Splunk payload.")
    parser.add_argument("--message-field", default="_raw", help="Message field in Splunk payload.")
    parser.add_argument("--timestamp-field", default="_time", help="Timestamp field in Splunk payload.")

    parser.add_argument("--pull-limit", type=int, default=100, help="Limit for immediate connector pull.")
    parser.add_argument("--skip-pull", action="store_true", help="Only save connector; do not pull logs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    api_base_url = (args.api_base_url or os.getenv("OPENINCIDENT_API_BASE_URL") or "http://127.0.0.1:8000").strip()
    email = (args.email or os.getenv("OPENINCIDENT_EMAIL") or "").strip()
    password = args.password or os.getenv("OPENINCIDENT_PASSWORD") or ""
    splunk_url = (args.splunk_url or os.getenv("SPLUNK_URL") or "").strip()
    splunk_token = (args.splunk_token or os.getenv("SPLUNK_TOKEN") or "").strip()
    project_id = (args.project_id or os.getenv("OPENINCIDENT_PROJECT_ID") or "").strip() or None
    project_name = (args.project_name or os.getenv("OPENINCIDENT_PROJECT_NAME") or "").strip() or None

    if not email:
        raise ValueError("Missing email. Use --email or OPENINCIDENT_EMAIL.")
    if not password:
        password = getpass.getpass("OpenIncident password: ").strip()
    if not password:
        raise ValueError("Missing password. Use --password or OPENINCIDENT_PASSWORD.")
    if not splunk_url:
        raise ValueError("Missing Splunk URL. Use --splunk-url or SPLUNK_URL.")
    if not splunk_token:
        raise ValueError("Missing Splunk token. Use --splunk-token or SPLUNK_TOKEN.")

    client = OpenIncidentClient(
        api_base_url=api_base_url,
        verify_tls=not bool(args.insecure),
        timeout_seconds=max(1.0, args.timeout_seconds),
    )

    print(f"Authenticating against {api_base_url} ...")
    client.login(email=email, password=password)

    resolved_project_id = client.resolve_project_id(project_id=project_id, project_name=project_name)
    print(f"Using project_id={resolved_project_id}")

    connector_payload = {
        "url": splunk_url,
        "method": "POST",
        "headers": {"Authorization": f"Splunk {splunk_token}"},
        "query_params": {},
        "payload": {
            "search": args.search,
            "output_mode": "json",
            "earliest_time": args.earliest_time,
            "latest_time": args.latest_time,
            "count": str(max(1, args.count)),
        },
        "payload_encoding": "form",
        "enabled": True,
        "format": "splunk_jsonl",
        "entries_path": None,
        "level_field": args.level_field,
        "source_field": args.source_field,
        "message_field": args.message_field,
        "timestamp_field": args.timestamp_field,
    }

    saved = client.set_connector(project_id=resolved_project_id, connector_payload=connector_payload)
    print("Splunk connector saved.")
    print(f"Connector format={saved.get('format')} enabled={saved.get('enabled')}")

    if args.skip_pull:
        print("Skipping immediate pull (--skip-pull set).")
        return

    pulled = client.pull_connector_logs(project_id=resolved_project_id, limit=max(1, args.pull_limit))
    imported = pulled.get("imported_count")
    status = pulled.get("status")
    print(f"Pull complete. status={status} imported_count={imported}")


if __name__ == "__main__":
    main()
