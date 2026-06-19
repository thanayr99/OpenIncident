from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.app as appmod
from models import TestEnvironmentConfig, TestEnvironmentRunResult
from server.session_store import InMemorySessionStore
from server.test_environment import prepare_workspace, validate_test_environment_commands


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    original_store = appmod.session_store
    original_environment = appmod.environment
    original_database_url = os.environ.get("OPENINCIDENT_DATABASE_URL")

    test_db_path = (tmp_path / "openincident_safety.db").resolve().as_posix()
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
            "name": "Safety Owner",
            "email": "safety@example.com",
            "password": "password123",
        },
    )
    assert register.status_code == 200
    login = client.post(
        "/auth/login",
        json={
            "email": "safety@example.com",
            "password": "password123",
        },
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_test_environment_command_validator_rejects_destructive_commands() -> None:
    issues = validate_test_environment_commands(
        install_command="npm install",
        test_command="npm test && Remove-Item -Recurse C:\\",
    )

    assert issues
    assert any("control operators" in issue for issue in issues)
    assert any("destructive" in issue for issue in issues)


def test_test_environment_config_rejects_unsafe_command(client: TestClient) -> None:
    headers = _auth_headers(client)
    project_response = client.post(
        "/projects",
        headers=headers,
        json={
            "name": "Unsafe Command Project",
            "repository_url": "https://github.com/example/repo",
        },
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["project_id"]

    response = client.put(
        f"/projects/{project_id}/testing/environment",
        headers=headers,
        json={
            "repository_url": "https://github.com/example/repo",
            "install_command": "npm install",
            "test_command": "git reset --hard",
            "enabled": True,
        },
    )

    assert response.status_code == 400
    assert "destructive" in response.text


def test_test_environment_run_rejects_unsafe_override(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "package.json").write_text('{"scripts":{"test":"echo ok"}}', encoding="utf-8")

    headers = _auth_headers(client)
    project_response = client.post(
        "/projects",
        headers=headers,
        json={
            "name": "Unsafe Override Project",
            "repository_url": str(source),
        },
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["project_id"]

    config_response = client.put(
        f"/projects/{project_id}/testing/environment",
        headers=headers,
        json={
            "repository_url": str(source),
            "install_command": None,
            "test_command": "npm test",
            "enabled": True,
        },
    )
    assert config_response.status_code == 200

    response = client.post(
        f"/projects/{project_id}/testing/environment/run",
        headers=headers,
        json={
            "pull_latest": False,
            "run_install": False,
            "run_tests": True,
            "test_command_override": "npm test && git clean -xdf",
        },
    )

    assert response.status_code == 400
    assert "control operators" in response.text


def test_test_environment_job_records_completed_result(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()

    headers = _auth_headers(client)
    project_response = client.post(
        "/projects",
        headers=headers,
        json={
            "name": "Async Job Project",
            "repository_url": str(source),
        },
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["project_id"]

    config_response = client.put(
        f"/projects/{project_id}/testing/environment",
        headers=headers,
        json={
            "repository_url": str(source),
            "install_command": None,
            "test_command": "pytest",
            "enabled": True,
        },
    )
    assert config_response.status_code == 200

    def fake_run_test_environment(config, request):  # noqa: ANN001
        return TestEnvironmentRunResult(
            project_id=config.project_id,
            repository_url=config.repository_url,
            branch=config.branch,
            workspace_path=str(source),
            pull_latest=request.pull_latest,
            run_install=request.run_install,
            run_tests=request.run_tests,
            success=True,
            summary="Repository tests passed in the mocked job.",
        )

    monkeypatch.setattr(appmod, "run_test_environment", fake_run_test_environment)

    queue_response = client.post(
        f"/projects/{project_id}/jobs/test-environment",
        headers=headers,
        json={
            "pull_latest": False,
            "run_install": False,
            "run_tests": True,
        },
    )
    assert queue_response.status_code == 200
    job_id = queue_response.json()["job_id"]

    job_response = client.get(f"/jobs/{job_id}", headers=headers)
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "succeeded"
    assert job["result"]["test_environment_run"]["success"] is True

    list_response = client.get(f"/projects/{project_id}/jobs", headers=headers)
    assert list_response.status_code == 200
    assert any(item["job_id"] == job_id for item in list_response.json())


def test_prepare_workspace_rejects_workdir_outside_workspace(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "package.json").write_text('{"scripts":{"test":"echo ok"}}', encoding="utf-8")
    config = TestEnvironmentConfig(
        project_id="project-1",
        repository_url=str(source),
        workdir="..",
    )

    with pytest.raises(ValueError, match="inside the prepared repository workspace"):
        prepare_workspace(config, base_dir=tmp_path / "envs", pull_latest=False)
