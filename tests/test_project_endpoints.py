from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

os.environ["OPENINCIDENT_DATABASE_URL"] = "sqlite:///data/openincident_pytest.db"

import server.app as appmod
from server.session_store import InMemorySessionStore


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    original_store = appmod.session_store
    original_environment = appmod.environment
    original_database_url = os.environ.get("OPENINCIDENT_DATABASE_URL")

    test_db_path = (tmp_path / "openincident_endpoints.db").resolve().as_posix()
    os.environ["OPENINCIDENT_DATABASE_URL"] = f"sqlite:///{test_db_path}"
    store = InMemorySessionStore()
    appmod.session_store = store
    _, _, environment = store.create_session(persist=False)
    appmod.environment = environment

    with TestClient(appmod.app) as test_client:
        yield test_client

    appmod.session_store = original_store
    appmod.environment = original_environment
    if original_database_url is None:
        os.environ.pop("OPENINCIDENT_DATABASE_URL", None)
    else:
        os.environ["OPENINCIDENT_DATABASE_URL"] = original_database_url


def _auth_headers(client: TestClient, *, email: str) -> dict[str, str]:
    register = client.post(
        "/auth/register",
        json={
            "name": email.split("@")[0],
            "email": email,
            "password": "password123",
        },
    )
    assert register.status_code == 200

    login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "password123",
        },
    )
    assert login.status_code == 200
    token = login.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _create_project_with_two_endpoints(client: TestClient, headers: dict[str, str]) -> dict:
    create_response = client.post(
        "/projects",
        headers=headers,
        json={
            "name": "Dual Endpoint Project",
            "repository_url": "https://github.com/example/repo",
            "endpoints": [
                {
                    "endpoint_id": "frontend",
                    "label": "Frontend Vercel",
                    "surface": "frontend",
                    "base_url": "https://frontend.example.com",
                    "healthcheck_path": "/",
                },
                {
                    "endpoint_id": "backend",
                    "label": "Backend Railway",
                    "surface": "api",
                    "base_url": "https://api.example.com",
                    "healthcheck_path": "/health",
                },
            ],
        },
    )
    assert create_response.status_code == 200
    return create_response.json()


def test_project_endpoints_can_be_created_and_listed(client: TestClient) -> None:
    headers = _auth_headers(client, email="endpoints-owner@example.com")
    project = _create_project_with_two_endpoints(client, headers)

    assert project["base_url"] == "https://frontend.example.com"
    assert len(project["endpoints"]) == 2
    assert {endpoint["surface"] for endpoint in project["endpoints"]} == {"frontend", "api"}

    list_response = client.get(f"/projects/{project['project_id']}/endpoints", headers=headers)
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 2
    assert any(endpoint["endpoint_id"] == "frontend" for endpoint in listed)
    assert any(endpoint["endpoint_id"] == "backend" for endpoint in listed)


def test_checks_auto_route_to_matching_surface(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _auth_headers(client, email="routing-owner@example.com")
    project = _create_project_with_two_endpoints(client, headers)
    project_id = project["project_id"]

    captured_api_urls: list[str] = []
    captured_browser_urls: list[str] = []

    class MockApiResponse:
        status_code = 200
        text = "ok"

    def fake_requests_request(method: str, url: str, **kwargs):  # noqa: ANN001
        captured_api_urls.append(url)
        return MockApiResponse()

    def fake_run_http_browser_check(target_url: str, request):  # noqa: ANN001
        captured_browser_urls.append(target_url)
        return {
            "status": "healthy",
            "status_code": 200,
            "response_time_ms": 12.3,
            "error_message": None,
            "response_excerpt": "ok",
            "engine": "http",
            "observed_url": target_url,
            "page_title": "Login",
        }

    monkeypatch.setattr(appmod.requests, "request", fake_requests_request)
    monkeypatch.setattr(appmod, "run_http_browser_check", fake_run_http_browser_check)

    api_check = client.post(
        f"/projects/{project_id}/checks/api",
        headers=headers,
        json={
            "method": "GET",
            "path": "/health",
            "expected_status": 200,
            "label": "API smoke",
        },
    )
    assert api_check.status_code == 200
    api_payload = api_check.json()
    assert api_payload["endpoint_id"] == "backend"
    assert api_payload["target_url"].startswith("https://api.example.com/")
    assert captured_api_urls and captured_api_urls[-1].startswith("https://api.example.com/")

    browser_check = client.post(
        f"/projects/{project_id}/checks/browser",
        headers=headers,
        json={
            "path": "/login",
            "label": "Frontend smoke",
            "browser_mode": "http",
        },
    )
    assert browser_check.status_code == 200
    browser_payload = browser_check.json()
    assert browser_payload["endpoint_id"] == "frontend"
    assert browser_payload["target_url"].startswith("https://frontend.example.com/")
    assert captured_browser_urls and captured_browser_urls[-1].startswith("https://frontend.example.com/")
