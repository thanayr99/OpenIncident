from __future__ import annotations

from datetime import datetime, timezone
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


class StoryDomain(str, Enum):
    FRONTEND = "frontend"
    API = "api"
    DATABASE = "database"
    AUTH = "auth"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    DEPLOYMENT = "deployment"
    UNKNOWN = "unknown"


class StoryStatus(str, Enum):
    PENDING = "pending"
    ANALYZED = "analyzed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class StoryTestType(str, Enum):
    BROWSER = "browser"
    API = "api"
    HEALTH = "health"
    DATABASE = "database"
    LOG_REVIEW = "log_review"
    CODE_REVIEW = "code_review"
    MANUAL_REVIEW = "manual_review"
    NONE = "none"


class StoryExecutionPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentRole(str, Enum):
    PLANNER = "planner"
    FRONTEND_TESTER = "frontend_tester"
    API_TESTER = "api_tester"
    DATABASE_ANALYST = "database_analyst"
    RELIABILITY_ANALYST = "reliability_analyst"
    TEST_ENV_GUARDIAN = "test_env_guardian"
    OVERSIGHT = "oversight"


class AgentMaturity(str, Enum):
    BOOTSTRAP = "bootstrap"
    LEARNING = "learning"
    OPERATIONAL = "operational"
    SPECIALIST = "specialist"
    LEAD = "lead"


class AgentTrainingStrategy(str, Enum):
    REINFORCEMENT_LEARNING = "reinforcement_learning"
    SUPERVISED_EVAL = "supervised_eval"
    HEURISTIC_TOOLING = "heuristic_tooling"
    HYBRID = "hybrid"


class AgentTrainingProfile(BaseModel):
    agent_id: str
    display_name: str
    mapped_roles: List[str] = Field(default_factory=list)
    recommended_strategy: AgentTrainingStrategy
    trainable_now: bool = False
    primary_environment: Optional[str] = None
    current_state: str
    why_this_strategy: str
    required_data: List[str] = Field(default_factory=list)
    next_milestone: str


class AgentTrainingPlan(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str
    next_global_steps: List[str] = Field(default_factory=list)
    profiles: List[AgentTrainingProfile] = Field(default_factory=list)


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


class ProjectEndpoint(BaseModel):
    endpoint_id: str
    label: str
    base_url: str
    surface: str = "general"
    healthcheck_path: str = "/health"
    metadata: Dict[str, str] = Field(default_factory=dict)


class ProjectEndpointInput(BaseModel):
    endpoint_id: Optional[str] = None
    label: str
    base_url: str
    surface: str = "general"
    healthcheck_path: str = "/health"
    metadata: Dict[str, str] = Field(default_factory=dict)


class ProjectEndpointBatchUpdateRequest(BaseModel):
    endpoints: List[ProjectEndpointInput]


class ProjectConfig(BaseModel):
    project_id: str
    name: str
    base_url: Optional[str] = None
    repository_url: Optional[str] = None
    healthcheck_path: str = "/health"
    endpoints: List[ProjectEndpoint] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class AgentProfile(BaseModel):
    agent_id: str
    project_id: str
    role: AgentRole
    display_name: str
    specialization: str
    maturity: AgentMaturity = AgentMaturity.BOOTSTRAP
    trust_score: float = 0.5
    completed_tasks: int = 0
    failed_tasks: int = 0
    stories_validated: int = 0
    incidents_triaged: int = 0
    notes: List[str] = Field(default_factory=list)
    last_active_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectAgentRoster(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agents: List[AgentProfile] = Field(default_factory=list)


class AgentCoordinationEntry(BaseModel):
    entry_id: str
    project_id: str
    from_role: Optional[AgentRole] = None
    to_role: AgentRole
    handoff_type: str
    summary: str
    related_story_id: Optional[str] = None
    related_run_id: Optional[str] = None
    related_session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectAgentCoordinationTrace(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entries: List[AgentCoordinationEntry] = Field(default_factory=list)


class AgentConversationMessage(BaseModel):
    message_id: str
    project_id: str
    sender_role: AgentRole
    recipient_role: Optional[AgentRole] = None
    message_type: str = "handoff_note"
    content: str
    related_story_id: Optional[str] = None
    related_run_id: Optional[str] = None
    related_session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectAgentConversationTrace(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: List[AgentConversationMessage] = Field(default_factory=list)


class ProjectCreateRequest(BaseModel):
    project_id: Optional[str] = None
    name: str
    base_url: Optional[str] = None
    repository_url: Optional[str] = None
    healthcheck_path: str = "/health"
    endpoints: List[ProjectEndpointInput] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class AuthRegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    team: str = ""


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthAccount(BaseModel):
    account_id: str
    name: str
    email: str
    team: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StoredAuthAccount(AuthAccount):
    password_hash: str


class AuthLoginResponse(BaseModel):
    token: str
    account: AuthAccount


class WebsiteMonitorConfig(BaseModel):
    project_id: str
    endpoint_id: Optional[str] = None
    base_url: str
    healthcheck_path: str = "/health"
    expected_status: int = 200
    timeout_seconds: float = 10.0
    enabled: bool = True
    headers: Dict[str, str] = Field(default_factory=dict)


class WebsiteMonitorUpdateRequest(BaseModel):
    endpoint_id: Optional[str] = None
    base_url: Optional[str] = None
    healthcheck_path: Optional[str] = "/health"
    expected_status: int = 200
    timeout_seconds: float = 10.0
    enabled: bool = True
    headers: Dict[str, str] = Field(default_factory=dict)


class WebsiteHealthSnapshot(BaseModel):
    project_id: str
    endpoint_id: Optional[str] = None
    endpoint_label: Optional[str] = None
    endpoint_surface: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "unknown"
    check_type: str = "health"
    target_url: str
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    response_excerpt: Optional[str] = None


class MonitorIncidentTrigger(BaseModel):
    enabled: bool = True
    failure_task_id: str = "easy"
    severity: str = "high"
    auto_create_run: bool = True


class ProjectApiCheckRequest(BaseModel):
    endpoint_id: Optional[str] = None
    method: str = "GET"
    path: str
    expected_status: int = 200
    timeout_seconds: float = 10.0
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    label: Optional[str] = None


class ProjectBrowserCheckRequest(BaseModel):
    endpoint_id: Optional[str] = None
    path: str = "/"
    expected_text: Optional[str] = None
    expected_selector: Optional[str] = None
    timeout_seconds: float = 10.0
    label: Optional[str] = None
    browser_mode: str = "http"
    wait_until: str = "networkidle"


class ProjectValidationSnapshot(BaseModel):
    project_id: str
    endpoint_id: Optional[str] = None
    endpoint_label: Optional[str] = None
    endpoint_surface: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    check_type: str
    label: str
    target_url: str
    status: str = "unknown"
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    response_excerpt: Optional[str] = None
    engine: str = "http"
    observed_url: Optional[str] = None
    page_title: Optional[str] = None


class TriageRecommendation(BaseModel):
    action_type: str
    rationale: str


class RunTriageSummary(BaseModel):
    run_id: str
    session_id: str
    status: str
    summary: str
    suspected_root_cause: str
    confidence: float
    evidence: List[str] = Field(default_factory=list)
    recommended_actions: List[TriageRecommendation] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionExecutionMode(str, Enum):
    SIMULATION = "simulation"
    RECOMMEND_ONLY = "recommend_only"
    GUARDED = "guarded"


class SessionExecutionPolicy(BaseModel):
    mode: SessionExecutionMode = SessionExecutionMode.SIMULATION
    allowed_actions: List[ActionType] = Field(default_factory=lambda: [action for action in ActionType])
    approval_required_actions: List[ActionType] = Field(default_factory=list)
    approval_token: Optional[str] = None
    blocked_reward: float = -0.25
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def simulation_default(cls) -> "SessionExecutionPolicy":
        return cls(
            mode=SessionExecutionMode.SIMULATION,
            allowed_actions=[action for action in ActionType],
            approval_required_actions=[],
            approval_token=None,
        )

    @classmethod
    def production_guarded_default(cls) -> "SessionExecutionPolicy":
        return cls(
            mode=SessionExecutionMode.GUARDED,
            allowed_actions=[action for action in ActionType],
            approval_required_actions=[
                ActionType.APPLY_FIX,
                ActionType.ROLLBACK_DEPLOY,
                ActionType.RESTART_SERVICE,
                ActionType.SCALE_SERVICE,
                ActionType.RESOLVE_INCIDENT,
            ],
            approval_token=None,
        )


class SessionExecutionPolicyUpdateRequest(BaseModel):
    mode: Optional[SessionExecutionMode] = None
    allowed_actions: Optional[List[ActionType]] = None
    approval_required_actions: Optional[List[ActionType]] = None
    approval_token: Optional[str] = None
    blocked_reward: Optional[float] = None


class SessionInfo(BaseModel):
    session_id: str
    task_id: str
    project: Optional[ProjectConfig] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionResetRequest(BaseModel):
    task_id: str = "easy"
    max_steps: int | None = None
    project_id: Optional[str] = None
    project: Optional[ProjectConfig] = None


class IncidentRun(BaseModel):
    run_id: str
    session_id: str
    task_id: str
    project: Optional[ProjectConfig] = None
    source: str = "manual"
    source_check_type: Optional[str] = None
    source_target_url: Optional[str] = None
    source_label: Optional[str] = None
    status: str = "investigating"
    trigger_reason: Optional[str] = None
    reward_history: List[float] = Field(default_factory=list)
    last_observation: Optional[IncidentObservation] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionResetResponse(BaseModel):
    session: SessionInfo
    run: IncidentRun
    observation: IncidentObservation


class SessionStepRequest(BaseModel):
    session_id: str
    action: IncidentAction
    approval_token: Optional[str] = None


class SessionStepResult(BaseModel):
    session: SessionInfo
    run: IncidentRun
    observation: IncidentObservation
    reward: float
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)


class UserStoryHint(BaseModel):
    path: Optional[str] = None
    expected_text: Optional[str] = None
    expected_selector: Optional[str] = None
    api_path: Optional[str] = None
    method: str = "GET"
    expected_status: int = 200
    health_path: Optional[str] = None
    database_target: Optional[str] = None


class UserStoryInput(BaseModel):
    story_id: Optional[str] = None
    title: str
    description: str
    acceptance_criteria: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    hints: UserStoryHint = Field(default_factory=UserStoryHint)


class UserStoryBatchCreateRequest(BaseModel):
    stories: List[UserStoryInput]


class UserStoryAnalysis(BaseModel):
    primary_domain: StoryDomain
    domains: List[StoryDomain] = Field(default_factory=list)
    assigned_agent: AgentRole
    suggested_test_types: List[StoryTestType] = Field(default_factory=list)
    domain_scores: Dict[str, float] = Field(default_factory=dict)
    confidence_score: float = 0.0
    execution_priority: StoryExecutionPriority = StoryExecutionPriority.MEDIUM
    planning_notes: List[str] = Field(default_factory=list)
    needs_repository_context: bool = False
    needs_runtime_validation: bool = True
    reasoning: str


class UserStoryExecutionResult(BaseModel):
    story_id: str
    project_id: str
    status: StoryStatus
    test_type: StoryTestType = StoryTestType.NONE
    success: bool = False
    summary: str
    evidence: List[str] = Field(default_factory=list)
    output: Dict[str, Any] = Field(default_factory=dict)
    linked_run_id: Optional[str] = None
    linked_session_id: Optional[str] = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserStoryRecord(BaseModel):
    story_id: str
    project_id: str
    title: str
    description: str
    acceptance_criteria: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    hints: UserStoryHint = Field(default_factory=UserStoryHint)
    status: StoryStatus = StoryStatus.PENDING
    analysis: Optional[UserStoryAnalysis] = None
    latest_result: Optional[UserStoryExecutionResult] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectStoryReport(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_stories: int = 0
    completed_stories: int = 0
    failed_stories: int = 0
    blocked_stories: int = 0
    pending_stories: int = 0
    progress_percent: float = 0.0
    stories: List[UserStoryRecord] = Field(default_factory=list)


class PlannerDomainBreakdown(BaseModel):
    domain: StoryDomain
    total_stories: int = 0
    assigned_agent: AgentRole
    suggested_test_types: List[StoryTestType] = Field(default_factory=list)
    high_priority_stories: int = 0


class ProjectPlannerSummary(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_stories: int = 0
    analyzed_stories: int = 0
    unclassified_stories: int = 0
    domain_breakdown: List[PlannerDomainBreakdown] = Field(default_factory=list)
    prioritized_story_ids: List[str] = Field(default_factory=list)
    next_recommended_actions: List[str] = Field(default_factory=list)
    stories: List[UserStoryRecord] = Field(default_factory=list)


class PlannerDecisionRecord(BaseModel):
    story_id: str
    project_id: str
    title: str
    created_at: datetime
    primary_domain: StoryDomain
    assigned_agent: AgentRole
    execution_priority: StoryExecutionPriority
    confidence_score: float = 0.0
    suggested_test_types: List[StoryTestType] = Field(default_factory=list)
    needs_repository_context: bool = False
    needs_runtime_validation: bool = True
    planning_notes: List[str] = Field(default_factory=list)
    domain_scores: Dict[str, float] = Field(default_factory=dict)
    final_status: Optional[StoryStatus] = None
    executed_test_type: Optional[StoryTestType] = None
    execution_success: Optional[bool] = None
    linked_run_id: Optional[str] = None
    linked_session_id: Optional[str] = None
    outcome_label: str = "pending"
    matched_assigned_agent: Optional[bool] = None


class ProjectPlannerTrainingDataset(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_records: int = 0
    analyzed_records: int = 0
    completed_records: int = 0
    failed_records: int = 0
    blocked_records: int = 0
    pending_records: int = 0
    route_match_rate: float = 0.0
    records: List[PlannerDecisionRecord] = Field(default_factory=list)


class PredeployValidationResult(BaseModel):
    project_id: str
    guardian_agent_id: str
    guardian_maturity: AgentMaturity
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_stories: int = 0
    completed_stories: int = 0
    failed_stories: int = 0
    blocked_stories: int = 0
    pending_stories: int = 0
    release_ready: bool = False
    summary: str = ""
    executed_story_ids: List[str] = Field(default_factory=list)
    stories: List[UserStoryRecord] = Field(default_factory=list)


class RepoCodeMatch(BaseModel):
    path: str
    score: float
    reason: str
    snippet: Optional[str] = None


class RepoInspectionResult(BaseModel):
    project_id: str
    repository_url: str
    query: str
    default_branch: Optional[str] = None
    matches: List[RepoCodeMatch] = Field(default_factory=list)
    error_message: Optional[str] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FrontendRouteCandidate(BaseModel):
    route: str
    source_path: str
    route_type: str = "page"
    score: float = 0.0


class FrontendSurfaceDiscovery(BaseModel):
    project_id: str
    repository_url: str
    framework: Optional[str] = None
    app_root: Optional[str] = None
    routes: List[FrontendRouteCandidate] = Field(default_factory=list)
    error_message: Optional[str] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FrontendStoryTestPlan(BaseModel):
    story_id: str
    project_id: str
    inferred_route: Optional[str] = None
    candidate_routes: List[FrontendRouteCandidate] = Field(default_factory=list)
    expected_text: Optional[str] = None
    expected_selector: Optional[str] = None
    browser_mode: str = "playwright"
    reasoning: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FrontendTrainingRecord(BaseModel):
    story_id: str
    project_id: str
    title: str
    created_at: datetime
    primary_domain: Optional[StoryDomain] = None
    assigned_agent: Optional[AgentRole] = None
    inferred_route: Optional[str] = None
    expected_text: Optional[str] = None
    expected_selector: Optional[str] = None
    browser_mode: Optional[str] = None
    reasoning: str = ""
    candidate_route_count: int = 0
    route_hint_match: Optional[bool] = None
    final_status: Optional[StoryStatus] = None
    execution_success: Optional[bool] = None
    executed_target_url: Optional[str] = None
    observed_url: Optional[str] = None
    page_title: Optional[str] = None
    error_message: Optional[str] = None
    linked_run_id: Optional[str] = None
    linked_session_id: Optional[str] = None
    outcome_label: str = "pending"


class ProjectFrontendTrainingDataset(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_records: int = 0
    planned_records: int = 0
    successful_records: int = 0
    failed_records: int = 0
    blocked_records: int = 0
    pending_records: int = 0
    route_hint_match_rate: float = 0.0
    expected_text_coverage_rate: float = 0.0
    selector_coverage_rate: float = 0.0
    records: List[FrontendTrainingRecord] = Field(default_factory=list)


class ApiTrainingRecord(BaseModel):
    story_id: str
    project_id: str
    title: str
    created_at: datetime
    primary_domain: Optional[StoryDomain] = None
    assigned_agent: Optional[AgentRole] = None
    expected_method: str = "GET"
    inferred_path: Optional[str] = None
    expected_status: int = 200
    has_explicit_api_hint: bool = False
    reasoning: str = ""
    final_status: Optional[StoryStatus] = None
    execution_success: Optional[bool] = None
    actual_status: Optional[int] = None
    response_time_ms: Optional[float] = None
    target_url: Optional[str] = None
    response_excerpt: Optional[str] = None
    error_message: Optional[str] = None
    linked_run_id: Optional[str] = None
    linked_session_id: Optional[str] = None
    outcome_label: str = "pending"
    status_match: Optional[bool] = None


class ProjectApiTrainingDataset(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_records: int = 0
    planned_records: int = 0
    successful_records: int = 0
    failed_records: int = 0
    blocked_records: int = 0
    pending_records: int = 0
    explicit_hint_rate: float = 0.0
    status_match_rate: float = 0.0
    records: List[ApiTrainingRecord] = Field(default_factory=list)


class GuardianDecisionRecord(BaseModel):
    validation_id: str
    project_id: str
    guardian_agent_id: str
    guardian_maturity: AgentMaturity
    started_at: datetime
    completed_at: datetime
    story_count: int = 0
    completed_stories: int = 0
    failed_stories: int = 0
    blocked_stories: int = 0
    pending_stories: int = 0
    release_ready: bool = False
    open_incident_count: int = 0
    latest_check_status: Optional[str] = None
    summary: str = ""
    decision_label: str = "blocked"
    executed_story_ids: List[str] = Field(default_factory=list)


class ProjectGuardianTrainingDataset(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_decisions: int = 0
    ready_decisions: int = 0
    blocked_decisions: int = 0
    decisions_with_open_incidents: int = 0
    healthy_ready_rate: float = 0.0
    records: List[GuardianDecisionRecord] = Field(default_factory=list)


class TriageTrainingRecord(BaseModel):
    triage_id: str
    project_id: str
    run_id: str
    session_id: str
    task_id: str
    run_status: str
    incident_source: str = "manual"
    confidence: float = 0.0
    suspected_root_cause: str = ""
    summary: str = ""
    evidence_count: int = 0
    recommendation_count: int = 0
    recommended_action_types: List[str] = Field(default_factory=list)
    open_incident_count: int = 0
    service_restored: bool = False
    root_cause_confirmed: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectTriageTrainingDataset(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_triages: int = 0
    average_confidence: float = 0.0
    restored_triage_rate: float = 0.0
    root_cause_confirmed_rate: float = 0.0
    recommendation_coverage_rate: float = 0.0
    records: List[TriageTrainingRecord] = Field(default_factory=list)


class ObservabilityTrainingRecord(BaseModel):
    record_id: str
    project_id: str
    check_type: str
    label: str
    target_url: str
    status: str
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    log_error_entries: int = 0
    log_warning_entries: int = 0
    top_signals: List[str] = Field(default_factory=list)
    degraded_metrics: List[str] = Field(default_factory=list)
    active_incident_count: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectObservabilityTrainingDataset(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_records: int = 0
    unhealthy_records: int = 0
    healthy_records: int = 0
    records_with_log_errors: int = 0
    records_with_degraded_metrics: int = 0
    incident_link_rate: float = 0.0
    records: List[ObservabilityTrainingRecord] = Field(default_factory=list)


class OversightAuditRecord(BaseModel):
    audit_id: str
    project_id: str
    timestamp: datetime
    source_role: Optional[AgentRole] = None
    audit_type: str
    summary: str
    related_story_id: Optional[str] = None
    related_run_id: Optional[str] = None
    related_session_id: Optional[str] = None
    linked_story_status: Optional[StoryStatus] = None
    linked_run_status: Optional[str] = None
    confidence_signal: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProjectOversightTrainingDataset(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_audits: int = 0
    run_linked_audits: int = 0
    story_linked_audits: int = 0
    resolved_run_audit_rate: float = 0.0
    completed_story_audit_rate: float = 0.0
    records: List[OversightAuditRecord] = Field(default_factory=list)


class EnvironmentWorkspaceInsight(BaseModel):
    workspace_path: str
    framework: Optional[str] = None
    app_root: Optional[str] = None
    package_manager: Optional[str] = None
    detected_files: List[str] = Field(default_factory=list)
    recommended_install_command: Optional[str] = None
    recommended_test_command: Optional[str] = None
    recommended_workdir: Optional[str] = None
    route_count: int = 0
    notes: List[str] = Field(default_factory=list)


class ProjectEnvironmentSummary(BaseModel):
    project_id: str
    repository_url: Optional[str] = None
    base_url: Optional[str] = None
    repository_connected: bool = False
    deployment_connected: bool = False
    workspace_ready: bool = False
    workspace_path: Optional[str] = None
    last_run_success: Optional[bool] = None
    last_run_summary: Optional[str] = None
    shell: Optional[str] = None
    branch: Optional[str] = None
    framework: Optional[str] = None
    app_root: Optional[str] = None
    route_count: int = 0
    recommended_install_command: Optional[str] = None
    recommended_test_command: Optional[str] = None
    recommended_workdir: Optional[str] = None
    next_actions: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectLogEntryInput(BaseModel):
    timestamp: Optional[datetime] = None
    level: str = "INFO"
    source: str = "application"
    message: str
    context: Dict[str, Any] = Field(default_factory=dict)


class ProjectLogEntry(BaseModel):
    log_id: str
    project_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    level: str = "INFO"
    source: str = "application"
    message: str
    context: Dict[str, Any] = Field(default_factory=dict)


class ProjectLogBatchRequest(BaseModel):
    entries: List[ProjectLogEntryInput]


class ProjectLogConnectorConfig(BaseModel):
    project_id: str
    url: str
    method: str = "GET"
    headers: Dict[str, str] = Field(default_factory=dict)
    query_params: Dict[str, str] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)
    payload_encoding: str = "json"
    enabled: bool = True
    format: str = "text"
    entries_path: Optional[str] = None
    level_field: str = "level"
    source_field: str = "source"
    message_field: str = "message"
    timestamp_field: str = "timestamp"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_pulled_at: Optional[datetime] = None
    last_pull_success: Optional[bool] = None
    last_pull_summary: Optional[str] = None
    last_pull_error: Optional[str] = None
    last_fetched_entries: int = 0
    last_imported_entries: int = 0
    consecutive_failures: int = 0


class ProjectLogConnectorRequest(BaseModel):
    url: str
    method: str = "GET"
    headers: Dict[str, str] = Field(default_factory=dict)
    query_params: Dict[str, str] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)
    payload_encoding: str = "json"
    enabled: bool = True
    format: str = "text"
    entries_path: Optional[str] = None
    level_field: str = "level"
    source_field: str = "source"
    message_field: str = "message"
    timestamp_field: str = "timestamp"


class ProjectLogConnectorPullRequest(BaseModel):
    limit: int = 100


class ProjectLogConnectorPullResult(BaseModel):
    project_id: str
    success: bool = False
    fetched_entries: int = 0
    imported_entries: int = 0
    summary: str = ""
    pulled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sample_messages: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class ProjectLogSummary(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_entries: int = 0
    error_entries: int = 0
    warning_entries: int = 0
    top_signals: List[str] = Field(default_factory=list)
    latest_errors: List[str] = Field(default_factory=list)


class ProjectDiagnosticIssue(BaseModel):
    severity: str = "info"
    category: str = "system"
    title: str
    detail: str


class ProjectDiagnosticSweepResult(BaseModel):
    project_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    health_snapshot: Optional[WebsiteHealthSnapshot] = None
    browser_snapshot: Optional[ProjectValidationSnapshot] = None
    api_snapshot: Optional[ProjectValidationSnapshot] = None
    log_summary: Optional[ProjectLogSummary] = None
    log_findings: List[str] = Field(default_factory=list)
    open_incident_ids: List[str] = Field(default_factory=list)
    triaged_run_ids: List[str] = Field(default_factory=list)
    agent_handoffs_recorded: int = 0
    issues: List[ProjectDiagnosticIssue] = Field(default_factory=list)
    summary: str = ""


class ProjectMetricPointInput(BaseModel):
    timestamp: Optional[datetime] = None
    name: str
    value: float
    unit: Optional[str] = None
    source: str = "system"
    dimensions: Dict[str, str] = Field(default_factory=dict)


class ProjectMetricPoint(BaseModel):
    metric_id: str
    project_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    name: str
    value: float
    unit: Optional[str] = None
    source: str = "system"
    dimensions: Dict[str, str] = Field(default_factory=dict)


class ProjectMetricBatchRequest(BaseModel):
    points: List[ProjectMetricPointInput]


class ProjectMetricSeries(BaseModel):
    name: str
    latest_value: float
    latest_unit: Optional[str] = None
    latest_source: str = "system"
    points: List[ProjectMetricPoint] = Field(default_factory=list)


class ProjectMetricSummary(BaseModel):
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_points: int = 0
    latest_values: Dict[str, float] = Field(default_factory=dict)
    units: Dict[str, str] = Field(default_factory=dict)
    degraded_metrics: List[str] = Field(default_factory=list)
    series: List[ProjectMetricSeries] = Field(default_factory=list)


class TestEnvironmentConfig(BaseModel):
    project_id: str
    repository_url: str
    branch: Optional[str] = None
    install_command: Optional[str] = None
    test_command: str = "pytest"
    workdir: Optional[str] = None
    enabled: bool = True
    shell: str = "powershell"
    env: Dict[str, str] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TestEnvironmentConfigRequest(BaseModel):
    repository_url: Optional[str] = None
    branch: Optional[str] = None
    install_command: Optional[str] = None
    test_command: str = "pytest"
    workdir: Optional[str] = None
    enabled: bool = True
    shell: str = "powershell"
    env: Dict[str, str] = Field(default_factory=dict)


class TestEnvironmentRunRequest(BaseModel):
    pull_latest: bool = True
    run_install: bool = True
    run_tests: bool = True
    install_command_override: Optional[str] = None
    test_command_override: Optional[str] = None
    timeout_seconds: float = 900.0


class TestEnvironmentCommandResult(BaseModel):
    command: str
    return_code: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    success: bool = False


class TestEnvironmentRunResult(BaseModel):
    project_id: str
    repository_url: str
    branch: Optional[str] = None
    workspace_path: str
    pull_latest: bool = True
    run_install: bool = True
    run_tests: bool = True
    install_result: Optional[TestEnvironmentCommandResult] = None
    test_result: Optional[TestEnvironmentCommandResult] = None
    success: bool = False
    summary: str = ""
    linked_run_id: Optional[str] = None
    linked_session_id: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectEvent(BaseModel):
    event_id: str
    project_id: str
    event_type: str
    title: str
    message: str
    severity: str = "info"
    source: str = "system"
    related_run_id: Optional[str] = None
    related_session_id: Optional[str] = None
    related_story_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectCommandCenterSummary(BaseModel):
    project: ProjectConfig
    agent_roster: Optional[ProjectAgentRoster] = None
    coordination_trace: Optional[ProjectAgentCoordinationTrace] = None
    conversation_trace: Optional[ProjectAgentConversationTrace] = None
    latest_health: Optional[WebsiteHealthSnapshot] = None
    latest_check: Optional[ProjectValidationSnapshot] = None
    story_report: Optional[ProjectStoryReport] = None
    log_summary: Optional[ProjectLogSummary] = None
    log_connector: Optional[ProjectLogConnectorConfig] = None
    metric_summary: Optional[ProjectMetricSummary] = None
    active_runs: List[IncidentRun] = Field(default_factory=list)
    recent_events: List[ProjectEvent] = Field(default_factory=list)


class DatabaseTableStat(BaseModel):
    table_name: str
    row_count: int = 0


class DatabaseOverview(BaseModel):
    engine: str
    database_url: str
    app_state_namespaces: int = 0
    tables: List[DatabaseTableStat] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DatabaseRowView(BaseModel):
    table_name: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class DatabaseTableRows(BaseModel):
    table_name: str
    limit: int = 50
    rows: List[DatabaseRowView] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DatabaseMigrationRecord(BaseModel):
    version: str
    description: str
    applied_at: datetime | None = None


class DatabaseMigrationStatus(BaseModel):
    engine: str
    current_version: str
    migrations: List[DatabaseMigrationRecord] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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
