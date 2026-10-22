from __future__ import annotations

from datetime import datetime, timezone
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


def _headers(client: TestClient, name: str, email: str) -> dict[str, str]:
    registered = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": "password123"},
    )
    assert registered.status_code in {200, 201}
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _project_and_run(client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    created = client.post(
        "/projects",
        headers=headers,
        json={
            "name": "Workflow Test Project",
            "repository_url": "https://github.com/example/workflow-test",
            "metadata": {},
        },
    )
    assert created.status_code == 200, created.text
    project = appmod.ProjectConfig.model_validate(created.json())
    _, run, _ = appmod.session_store.create_session(
        task_id="easy",
        project=project,
        source="test",
        trigger_reason="workflow test",
    )
    return project.project_id, run.run_id


def _event(status: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": status,
        "agent_role": "test-agent",
        "event_type": "test_event",
        "summary": f"Transition to {status}",
        "evidence": [{"kind": "test", "reference": "unit-test"}],
        "confidence": 0.8,
    }
    payload.update(overrides)
    return payload


def test_incident_workflow_records_ordered_evidence_and_rejects_invalid_transition(
    client: TestClient,
) -> None:
    headers = _headers(client, "Owner", "workflow-owner@example.com")
    project_id, run_id = _project_and_run(client, headers)
    url = f"/projects/{project_id}/incidents/{run_id}/workflow"

    invalid_first = client.post(url, headers=headers, json=_event("investigating"))
    assert invalid_first.status_code == 409

    for status in ("detected", "investigating", "testing", "awaiting_approval"):
        response = client.post(url, headers=headers, json=_event(status))
        assert response.status_code == 201, response.text
        assert response.json()["status"] == status

    agent_resolution = client.post(url, headers=headers, json=_event("resolved"))
    assert agent_resolution.status_code == 403

    approval = client.post(
        f"/projects/{project_id}/incidents/{run_id}/approve",
        headers=headers,
        json={"summary": "Reviewed the evidence and approved resolution."},
    )
    assert approval.status_code == 201, approval.text
    assert approval.json()["status"] == "resolved"

    terminal_update = client.post(url, headers=headers, json=_event("investigating"))
    assert terminal_update.status_code == 409
    assert appmod.session_store.get_run_by_id(run_id).status == "resolved"

    timeline = client.get(url, headers=headers)
    assert timeline.status_code == 200
    records = timeline.json()
    assert [item["status"] for item in records] == [
        "detected", "investigating", "testing", "awaiting_approval", "resolved"
    ]
    assert records[1]["evidence"][0]["reference"] == "unit-test"
    assert records[1]["confidence"] == pytest.approx(0.8)
    assert all(item["run_id"] == run_id for item in records)


def test_incident_workflow_enforces_project_ownership_and_run_binding(
    client: TestClient,
) -> None:
    owner_headers = _headers(client, "Owner", "workflow-owner2@example.com")
    other_headers = _headers(client, "Other", "workflow-other@example.com")
    project_id, run_id = _project_and_run(client, owner_headers)
    url = f"/projects/{project_id}/incidents/{run_id}/workflow"

    assert client.get(url).status_code == 401
    assert client.get(url, headers=other_headers).status_code == 403

    # A run from a different project must not be exposed through this project's URL.
    other_project_id, _ = _project_and_run(client, owner_headers)
    mismatched = client.get(
        f"/projects/{other_project_id}/incidents/{run_id}/workflow",
        headers=owner_headers,
    )
    assert mismatched.status_code == 404

    first = client.post(url, headers=owner_headers, json=_event("detected"))
    assert first.status_code == 201

    approval_without_pending = client.post(
        f"/projects/{project_id}/incidents/{run_id}/approve",
        headers=owner_headers,
        json={"summary": "Should not be approved before the gate."},
    )
    assert approval_without_pending.status_code == 409


def test_investigate_endpoint_records_log_repository_and_triage_handoffs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    headers = _headers(client, "Investigator", "workflow-investigator@example.com")
    project_id, run_id = _project_and_run(client, headers)
    inspected: list[str] = []

    def fake_inspect(project, query: str):  # noqa: ANN001
        inspected.append(query)
        return SimpleNamespace(matches=[], error_message="mock repository inspection unavailable")

    monkeypatch.setattr(appmod, "inspect_repository_for_query", fake_inspect)

    response = client.post(
        f"/projects/{project_id}/incidents/{run_id}/investigate",
        headers=headers,
        json={"query": "API 500 stack trace"},
    )

    assert response.status_code == 200, response.text
    assert inspected == ["API 500 stack trace"]
    records = response.json()
    roles = [item["agent_role"] for item in records]
    assert "orchestrator" in roles
    assert "log_analyst" in roles
    assert "code_investigator" in roles
    assert "triage" in roles
    assert records[-1]["event_type"] == "triage_summary"
    assert appmod.session_store.get_run_by_id(run_id).status == "investigating"


def test_investigate_endpoint_rejects_cross_project_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _headers(client, "Owner", "workflow-owner3@example.com")
    project_id, _ = _project_and_run(client, headers)
    other_project_id, other_run_id = _project_and_run(client, headers)
    response = client.post(
        f"/projects/{project_id}/incidents/{other_run_id}/investigate",
        headers=headers,
        json={"query": "failure"},
    )
    assert response.status_code == 404


def test_guardian_review_blocks_when_story_check_and_incident_gates_are_unmet(
    client: TestClient,
) -> None:
    headers = _headers(client, "Guardian", "workflow-guardian@example.com")
    project_id, run_id = _project_and_run(client, headers)
    workflow_url = f"/projects/{project_id}/incidents/{run_id}/workflow"
    for status in ("detected", "investigating"):
        response = client.post(workflow_url, headers=headers, json=_event(status))
        assert response.status_code == 201, response.text

    response = client.post(
        f"/projects/{project_id}/incidents/{run_id}/guardian-review",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    review = response.json()
    assert review["agent_role"] == "test_guardian"
    assert review["event_type"] == "guardian_review"
    assert review["status"] == "investigating"
    guardian = next(item for item in review["evidence"] if item["kind"] == "guardian_decision")
    assert guardian["decision"] == "blocked"
    assert guardian["automatic_deploy"] is False
    assert len(guardian["blockers"]) >= 2
    assert "blocked" in review["summary"].lower()
    assert "No user stories are registered" in review["summary"]
    assert "No recorded validation check" in review["summary"]
    approval_request = client.post(
        f"/projects/{project_id}/incidents/{run_id}/request-approval",
        headers=headers,
    )
    assert approval_request.status_code == 409
    assert appmod.session_store.get_run_by_id(run_id).status == "investigating"


def test_guardian_review_rejects_run_from_another_project(
    client: TestClient,
) -> None:
    headers = _headers(client, "GuardianOwner", "workflow-guardian-owner@example.com")
    project_id, _ = _project_and_run(client, headers)
    other_project_id, other_run_id = _project_and_run(client, headers)
    response = client.post(
        f"/projects/{project_id}/incidents/{other_run_id}/guardian-review",
        headers=headers,
    )
    assert response.status_code == 404


def test_guardian_ready_review_requires_human_approval_before_resolution(
    client: TestClient,
) -> None:
    headers = _headers(client, "ReadyGuardian", "workflow-guardian-ready@example.com")
    project_id, run_id = _project_and_run(client, headers)
    story_response = client.post(
        f"/projects/{project_id}/stories",
        headers=headers,
        json={"stories": [{"title": "Health check", "description": "API health remains good", "acceptance_criteria": ["Health returns 200"], "tags": ["api"]}]},
    )
    assert story_response.status_code == 200, story_response.text
    story = appmod.session_store.get_story(story_response.json()[0]["story_id"])
    story.status = appmod.StoryStatus.COMPLETED
    appmod.session_store._stories[story.story_id] = story
    appmod.session_store._save()
    appmod.session_store.add_validation_snapshot(
        appmod.ProjectValidationSnapshot(
            project_id=project_id,
            check_type="health",
            label="Fresh health validation",
            target_url="https://example.com/health",
            status="healthy",
            checked_at=datetime.now(timezone.utc),
        )
    )
    workflow_url = f"/projects/{project_id}/incidents/{run_id}/workflow"
    for status in ("detected", "investigating"):
        response = client.post(workflow_url, headers=headers, json=_event(status))
        assert response.status_code == 201, response.text

    review = client.post(
        f"/projects/{project_id}/incidents/{run_id}/guardian-review",
        headers=headers,
    )
    assert review.status_code == 200, review.text
    decision = next(item for item in review.json()["evidence"] if item["kind"] == "guardian_decision")
    assert decision["decision"] == "ready_for_human_approval"

    request_approval = client.post(
        f"/projects/{project_id}/incidents/{run_id}/request-approval",
        headers=headers,
    )
    assert request_approval.status_code == 200, request_approval.text
    assert request_approval.json()[-1]["status"] == "awaiting_approval"
    assert appmod.session_store.get_run_by_id(run_id).status == "awaiting_approval"

    approval = client.post(
        f"/projects/{project_id}/incidents/{run_id}/approve",
        headers=headers,
        json={"summary": "Reviewed the evidence and approved incident resolution."},
    )
    assert approval.status_code == 201, approval.text
    assert approval.json()["status"] == "resolved"
    assert appmod.session_store.get_run_by_id(run_id).status == "resolved"
