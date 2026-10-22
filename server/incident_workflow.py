from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IncidentWorkflowStatus(str, Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    TESTING = "testing"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IncidentWorkflowEventRequest(BaseModel):
    status: IncidentWorkflowStatus
    agent_role: str = Field(min_length=1, max_length=80)
    event_type: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=2000)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class IncidentWorkflowApprovalRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)


class IncidentWorkflowEvent(BaseModel):
    event_id: str
    project_id: str
    run_id: str
    status: IncidentWorkflowStatus
    agent_role: str
    event_type: str
    summary: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


ALLOWED_TRANSITIONS: dict[IncidentWorkflowStatus | None, set[IncidentWorkflowStatus]] = {
    None: {IncidentWorkflowStatus.DETECTED},
    IncidentWorkflowStatus.DETECTED: {IncidentWorkflowStatus.INVESTIGATING, IncidentWorkflowStatus.FAILED, IncidentWorkflowStatus.CANCELLED},
    IncidentWorkflowStatus.INVESTIGATING: {IncidentWorkflowStatus.INVESTIGATING, IncidentWorkflowStatus.TESTING, IncidentWorkflowStatus.FAILED, IncidentWorkflowStatus.CANCELLED},
    IncidentWorkflowStatus.TESTING: {IncidentWorkflowStatus.INVESTIGATING, IncidentWorkflowStatus.AWAITING_APPROVAL, IncidentWorkflowStatus.FAILED, IncidentWorkflowStatus.CANCELLED},
    IncidentWorkflowStatus.AWAITING_APPROVAL: {IncidentWorkflowStatus.INVESTIGATING, IncidentWorkflowStatus.RESOLVED, IncidentWorkflowStatus.CANCELLED},
    IncidentWorkflowStatus.FAILED: {IncidentWorkflowStatus.INVESTIGATING, IncidentWorkflowStatus.CANCELLED},
    IncidentWorkflowStatus.RESOLVED: set(),
    IncidentWorkflowStatus.CANCELLED: set(),
}
