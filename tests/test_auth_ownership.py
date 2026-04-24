from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.app as appmod
from server.session_store import InMemorySessionStore


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    original_store = appmod.session_store
    original_environment = appmod.environment

    store = InMemorySessionStore(store_path=tmp_path / "store.json")
    appmod.session_store = store
    _, _, environment = store.create_session(persist=False)
    appmod.environment = environment

    with TestClient(appmod.app) as test_client:
        yield test_client

    appmod.session_store = original_store
    appmod.environment = original_environment


def _login_headers(client: TestClient, *, name: str, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={
            "name": name,
            "email": email,
            "password": "password123",
        },
    )
    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "password123",
        },
    )
    assert response.status_code == 200
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_project_ownership_guards(client: TestClient) -> None:
    owner_headers = _login_headers(client, name="User A", email="a@example.com")
    other_headers = _login_headers(client, name="User B", email="b@example.com")

    create_response = client.post(
        "/projects",
        headers=owner_headers,
        json={
            "name": "Project A",
            "repository_url": "https://github.com/example/repo",
            "metadata": {},
        },
    )
    assert create_response.status_code == 200
    project_id = create_response.json()["project_id"]

    no_auth_summary = client.get(f"/projects/{project_id}/summary")
    assert no_auth_summary.status_code == 401

    other_summary = client.get(f"/projects/{project_id}/summary", headers=other_headers)
    assert other_summary.status_code == 403

    owner_summary = client.get(f"/projects/{project_id}/summary", headers=owner_headers)
    assert owner_summary.status_code == 200

    projects_without_auth = client.get("/projects")
    assert projects_without_auth.status_code == 200
    assert all(project["project_id"] != project_id for project in projects_without_auth.json())

    projects_for_owner = client.get("/projects", headers=owner_headers)
    assert projects_for_owner.status_code == 200
    assert any(project["project_id"] == project_id for project in projects_for_owner.json())

    create_story_response = client.post(
        f"/projects/{project_id}/stories",
        headers=owner_headers,
        json={
            "stories": [
                {
                    "title": "Story 1",
                    "description": "Desc",
                }
            ]
        },
    )
    assert create_story_response.status_code == 200
    story_id = create_story_response.json()[0]["story_id"]

    other_analyze_response = client.post(f"/stories/{story_id}/analyze", headers=other_headers)
    assert other_analyze_response.status_code == 403
