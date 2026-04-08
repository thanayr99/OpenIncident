from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    INSPECT_LOGS = "inspect_logs"
    INSPECT_METRICS = "inspect_metrics"
    INSPECT_TRACES = "inspect_traces"
    INSPECT_DEPLOYS = "inspect_deploys"
    INSPECT_CONFIG = "inspect_config"
    INSPECT_CODE = "inspect_code"
    IDENTIFY_ROOT_CAUSE = "identify_root_cause"
    APPLY_FIX = "apply_fix"
    ROLLBACK_DEPLOY = "rollback_deploy"
    RESTART_SERVICE = "restart_service"
    SCALE_SERVICE = "scale_service"
    ADD_MONITOR = "add_monitor"
    RESOLVE_INCIDENT = "resolve_incident"
    DO_NOTHING = "do_nothing"


class IncidentAction(BaseModel):
    action_type: ActionType
    target: Optional[str] = None
    content: Optional[str] = None


class IncidentObservation(BaseModel):
    incident_id: str
    difficulty: str
    service_name: str
    incident_summary: str
    current_status: str
    severity: str
    user_impact: str
    logs: List[str] = Field(default_factory=list)
    metrics: Dict[str, float] = Field(default_factory=dict)
    traces: List[str] = Field(default_factory=list)
    recent_deploys: List[str] = Field(default_factory=list)
    config_snapshot: Dict[str, str] = Field(default_factory=dict)
    code_snippet: str = ""
    available_dashboards: List[str] = Field(default_factory=list)
    investigation_notes: List[str] = Field(default_factory=list)
    suspected_root_cause: Optional[str] = None
    root_cause_confirmed: bool = False
    mitigation_applied: bool = False
    service_restored: bool = False
    monitoring_added: bool = False
    passed_checks: int = 0
    failed_checks: int = 0
    reliability_score: float = 0.0
    steps_taken: int = 0
    max_steps: int = 0
    last_action: Optional[str] = None
    last_action_error: Optional[str] = None


class StepResult(BaseModel):
    observation: IncidentObservation
    reward: float
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)


class IncidentTask(BaseModel):
    task_id: str
    difficulty: str
    title: str
    service_name: str
    incident_summary: str
    severity: str
    user_impact: str
    initial_logs: List[str]
    hidden_logs: List[str] = Field(default_factory=list)
    initial_metrics: Dict[str, float]
    hidden_metrics: Dict[str, float] = Field(default_factory=dict)
    initial_traces: List[str]
    hidden_traces: List[str] = Field(default_factory=list)
    recent_deploys: List[str]
    config_snapshot: Dict[str, str]
    code_snippet: str
    available_dashboards: List[str]
    root_cause_keywords: List[str]
    valid_mitigations: List[str]
    partial_mitigations: List[str] = Field(default_factory=list)
    harmful_actions: List[str] = Field(default_factory=list)
    expected_checks: List[str]
    max_steps: int
    baseline_reliability: float
