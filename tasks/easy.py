from models import IncidentTask


TASK_EASY = IncidentTask(
    task_id="easy",
    difficulty="easy",
    title="Null Handling Bug In Profile API",
    service_name="profile-service",
    incident_summary="500 errors increased sharply on GET /profile after a recent deployment.",
    severity="high",
    user_impact="Users cannot load profile pages.",
    initial_logs=[
        "ERROR AttributeError: 'NoneType' object has no attribute 'strip'",
        "ERROR request_id=abc123 path=/profile status=500",
    ],
    hidden_logs=[
        "STACKTRACE normalize_display_name -> value.strip().lower()",
    ],
    initial_metrics={
        "error_rate": 18.4,
        "p95_latency_ms": 420.0,
        "request_success_rate": 81.6,
    },
    hidden_metrics={
        "profile_500_rate": 22.0,
    },
    initial_traces=[
        "GET /profile -> normalize_display_name -> exception",
    ],
    hidden_traces=[
        "span=normalize_display_name duration_ms=3 error=true",
    ],
    recent_deploys=[
        "deploy_1842: refactor profile normalization logic",
    ],
    config_snapshot={
        "PROFILE_CACHE_TTL": "300",
        "ENV": "production",
    },
    code_snippet=(
        "def normalize_display_name(value: str | None) -> str:\n"
        "    return value.strip().lower()\n"
    ),
    available_dashboards=[
        "api-errors",
        "profile-endpoint-health",
    ],
    root_cause_keywords=[
        "none",
        "null",
        "strip",
        "missing null check",
        "profile normalization",
    ],
    valid_mitigations=[
        "add null guard",
        "handle none before strip",
        "default empty string",
        "patch normalize_display_name",
    ],
    partial_mitigations=[
        "rollback deploy",
    ],
    harmful_actions=[
        "scale_service",
        "restart_service",
    ],
    expected_checks=[
        "error_rate_normalized",
        "endpoint_healthy",
        "root_cause_identified",
    ],
    max_steps=8,
    baseline_reliability=45.0,
)
