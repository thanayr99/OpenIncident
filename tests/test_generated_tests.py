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

    test_db_path = (tmp_path / "openincident_generated_tests.db").resolve().as_posix()
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


def _auth_headers(client: TestClient) -> dict[str, str]:
    register = client.post(
        "/auth/register",
        json={
            "name": "Generated Tests Owner",
            "email": "generated-tests@example.com",
            "password": "password123",
        },
    )
    assert register.status_code == 200
    login = client.post(
        "/auth/login",
        json={
            "email": "generated-tests@example.com",
            "password": "password123",
        },
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_generated_tests_cover_frontend_api_and_manual_domains(client: TestClient) -> None:
    headers = _auth_headers(client)
    project_response = client.post(
        "/projects",
        headers=headers,
        json={
            "name": "Generated Test Project",
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
                    "hints": {
                        "path": "/login",
                        "expected_text": "Sign in",
                    },
                },
                {
                    "title": "Profile API should respond",
                    "description": "GET /api/profile should return HTTP 200.",
                    "acceptance_criteria": ["Profile API returns success"],
                    "tags": ["api"],
                    "hints": {
                        "api_path": "/api/profile",
                        "expected_status": 200,
                    },
                },
                {
                    "title": "User preference should persist",
                    "description": "The selected theme should be saved in the database.",
                    "acceptance_criteria": ["Theme preference is stored"],
                    "tags": ["database"],
                },
            ]
        },
    )
    assert story_response.status_code == 200

    plan_response = client.get(f"/projects/{project_id}/generated-tests", headers=headers)
    assert plan_response.status_code == 200
    plan = plan_response.json()

    assert plan["total_cases"] == 3
    assert plan["browser_cases"] == 1
    assert plan["api_cases"] == 1
    assert plan["manual_cases"] == 1
    assert plan["automated_cases"] == 2

    browser_case = next(item for item in plan["cases"] if item["test_type"] == "browser")
    assert browser_case["target_path"] == "/login"
    assert browser_case["expected_text"] == "Sign in"
    assert browser_case["automation_ready"] is True

    api_case = next(item for item in plan["cases"] if item["test_type"] == "api")
    assert api_case["target_path"] == "/api/profile"
    assert api_case["method"] == "GET"
    assert api_case["expected_status"] == 200

    manual_case = next(item for item in plan["cases"] if item["test_type"] == "manual_review")
    assert manual_case["automation_ready"] is False
    assert "dedicated automated executor" in manual_case["blocked_reason"]


def test_generated_test_plan_job_executes_automation_ready_cases(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth_headers(client)
    project_response = client.post(
        "/projects",
        headers=headers,
        json={
            "name": "Generated Test Job Project",
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
                    "tags": ["frontend", "auth"],
                    "hints": {"path": "/login", "expected_text": "Sign in"},
                },
                {
                    "title": "Profile API should respond",
                    "description": "GET /api/profile should return HTTP 200.",
                    "tags": ["api"],
                    "hints": {"api_path": "/api/profile", "expected_status": 200},
                },
                {
                    "title": "User preference should persist",
                    "description": "The selected theme should be saved in the database.",
                    "tags": ["database"],
                },
            ]
        },
    )
    assert story_response.status_code == 200
    story_ids = [item["story_id"] for item in story_response.json()]
    executed_story_ids: list[str] = []

    def fake_execute_story(story_id: str, authorization: str | None):  # noqa: ANN001
        executed_story_ids.append(story_id)
        return UserStoryExecutionResult(
            story_id=story_id,
            project_id=project_id,
            status=StoryStatus.COMPLETED,
            test_type=StoryTestType.BROWSER,
            success=True,
            summary="Mock generated test passed.",
        )

    monkeypatch.setattr(appmod, "_execute_project_story_internal", fake_execute_story)

    queue_response = client.post(f"/projects/{project_id}/jobs/generated-tests", headers=headers)
    assert queue_response.status_code == 200
    job_id = queue_response.json()["job_id"]

    job_response = client.get(f"/jobs/{job_id}", headers=headers)
    assert job_response.status_code == 200
    job = job_response.json()

    assert job["status"] == "succeeded"
    assert job["result"]["executed_cases"] == 2
    assert job["result"]["passed_cases"] == 2
    assert job["result"]["skipped_cases"] == 1
    assert set(executed_story_ids) == set(story_ids[:2])
