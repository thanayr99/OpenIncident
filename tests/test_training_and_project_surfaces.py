from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

import server.app as appmod
from models import StoryStatus, StoryTestType, UserStoryExecutionResult
from server.session_store import InMemorySessionStore


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    original_store = appmod.session_store
    original_environment = appmod.environment
    original_database_url = os.environ.get("OPENINCIDENT_DATABASE_URL")

    test_db_path = (tmp_path / "openincident_training_surfaces.db").resolve().as_posix()
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
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _create_project_with_stories(client: TestClient, headers: dict[str, str]) -> tuple[str, list[str]]:
    project_response = client.post(
        "/projects",
        headers=headers,
        json={
            "name": "Training Dataset Project",
            "repository_url": "https://github.com/example/repo",
            "endpoints": [
                {
                    "endpoint_id": "frontend",
                    "label": "Frontend",
                    "surface": "frontend",
                    "base_url": "https://frontend.example.com",
                    "healthcheck_path": "/",
                },
                {
                    "endpoint_id": "backend",
                    "label": "Backend API",
                    "surface": "api",
                    "base_url": "https://api.example.com",
                    "healthcheck_path": "/health",
                },
            ],
        },
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["project_id"]

    story_response = client.post(
        f"/projects/{project_id}/stories",
        headers=headers,
        json={
            "stories": [
                {
                    "title": "Login page should render",
                    "description": "The login page should show the sign in form.",
                    "acceptance_criteria": ["Sign in is visible"],
                    "tags": ["frontend", "auth"],
                    "hints": {"path": "/login", "expected_text": "Sign in"},
                },
                {
                    "title": "Profile API should respond",
                    "description": "GET /api/profile should return HTTP 200.",
                    "acceptance_criteria": ["Profile API returns success"],
                    "tags": ["api"],
                    "hints": {"api_path": "/api/profile", "expected_status": 200},
                },
            ]
        },
    )
    assert story_response.status_code == 200
    return project_id, [story["story_id"] for story in story_response.json()]


def test_system_agent_training_plan_requires_auth_and_lists_agent_profiles(client: TestClient) -> None:
    unauthenticated = client.get("/system/agent-training-plan")
    assert unauthenticated.status_code == 401

    headers = _auth_headers(client, email="training-plan@example.com")
    response = client.get("/system/agent-training-plan", headers=headers)
    assert response.status_code == 200

    plan = response.json()
    profile_ids = {profile["agent_id"] for profile in plan["profiles"]}
    assert "reliability_agent" in profile_ids
    assert "planner_agent" in profile_ids
    assert any(profile["trainable_now"] for profile in plan["profiles"])
    assert plan["next_global_steps"]


def test_project_training_datasets_are_owner_scoped_and_populated(client: TestClient) -> None:
    owner_headers = _auth_headers(client, email="training-owner@example.com")
    other_headers = _auth_headers(client, email="training-other@example.com")
    project_id, story_ids = _create_project_with_stories(client, owner_headers)

    for story_id in story_ids:
        analyze_response = client.post(f"/stories/{story_id}/analyze", headers=owner_headers)
        assert analyze_response.status_code == 200

    blocked_response = client.get(f"/projects/{project_id}/planner-training-dataset", headers=other_headers)
    assert blocked_response.status_code == 403

    planner_response = client.get(f"/projects/{project_id}/planner-training-dataset", headers=owner_headers)
    assert planner_response.status_code == 200
    planner_dataset = planner_response.json()
    assert planner_dataset["project_id"] == project_id
    assert len(planner_dataset["records"]) == 2
    assert {record["assigned_agent"] for record in planner_dataset["records"]} >= {"frontend_tester", "api_tester"}

    frontend_response = client.get(f"/projects/{project_id}/frontend-training-dataset", headers=owner_headers)
    assert frontend_response.status_code == 200
    frontend_dataset = frontend_response.json()
    assert frontend_dataset["total_records"] >= 1
    assert any(record["story_id"] == story_ids[0] for record in frontend_dataset["records"])

    api_response = client.get(f"/projects/{project_id}/api-training-dataset", headers=owner_headers)
    assert api_response.status_code == 200
    api_dataset = api_response.json()
    assert api_dataset["total_records"] >= 1
    assert any(record["story_id"] == story_ids[1] for record in api_dataset["records"])


def test_project_summary_agent_traces_and_events_share_project_context(client: TestClient) -> None:
    headers = _auth_headers(client, email="project-surfaces@example.com")
    project_id, story_ids = _create_project_with_stories(client, headers)

    analyze_response = client.post(f"/stories/{story_ids[0]}/analyze", headers=headers)
    assert analyze_response.status_code == 200

    summary_response = client.get(f"/projects/{project_id}/summary", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["project"]["project_id"] == project_id
    assert summary["agent_roster"]["agents"]
    assert summary["story_report"]["total_stories"] == 2

    agents_response = client.get(f"/projects/{project_id}/agents", headers=headers)
    assert agents_response.status_code == 200
    assert agents_response.json()["agents"]

    coordination_response = client.get(f"/projects/{project_id}/agents/coordination", headers=headers)
    assert coordination_response.status_code == 200
    assert coordination_response.json()["project_id"] == project_id

    conversation_response = client.get(f"/projects/{project_id}/agents/conversation", headers=headers)
    assert conversation_response.status_code == 200
    assert conversation_response.json()["project_id"] == project_id

    events_response = client.get(f"/projects/{project_id}/events", headers=headers)
    assert events_response.status_code == 200
    assert any(event["event_type"] == "story_created" for event in events_response.json())


def test_project_jobs_are_not_visible_to_other_accounts(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    owner_headers = _auth_headers(client, email="job-owner@example.com")
    other_headers = _auth_headers(client, email="job-other@example.com")
    project_id, _ = _create_project_with_stories(client, owner_headers)

    def fake_execute_story(story_id: str, authorization: str | None):  # noqa: ANN001
        return UserStoryExecutionResult(
            story_id=story_id,
            project_id=project_id,
            status=StoryStatus.COMPLETED,
            test_type=StoryTestType.API,
            success=True,
            summary="Mocked execution passed.",
        )

    monkeypatch.setattr(appmod, "_execute_project_story_internal", fake_execute_story)

    queue_response = client.post(f"/projects/{project_id}/jobs/generated-tests", headers=owner_headers)
    assert queue_response.status_code == 200
    job_id = queue_response.json()["job_id"]

    other_job_response = client.get(f"/jobs/{job_id}", headers=other_headers)
    assert other_job_response.status_code == 403

    owner_job_response = client.get(f"/jobs/{job_id}", headers=owner_headers)
    assert owner_job_response.status_code == 200
    assert owner_job_response.json()["job_id"] == job_id
