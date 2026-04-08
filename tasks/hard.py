from models import IncidentTask


TASK_HARD = IncidentTask(
    task_id="hard",
    difficulty="hard",
    title="Search Timeout Storm After Feature Rollout",
    service_name="search-service",
    incident_summary="Search latency and timeout rates spiked after a rollout. Logs suggest database instability, but impact keeps worsening.",
    severity="critical",
    user_impact="Search requests time out for many users and overall site engagement is dropping.",
    initial_logs=[
        "ERROR db timeout on query search_results",
        "WARN upstream timeout path=/search",
        "WARN worker queue depth high",
    ],
    hidden_logs=[
        "INFO feature_flag=expanded-results enabled=true",
        "DEBUG repeated downstream query execution detected",
    ],
    initial_metrics={
        "timeout_rate": 17.2,
        "p95_latency_ms": 4200.0,
        "cpu_usage": 91.0,
        "worker_utilization": 96.0,
    },
    hidden_metrics={
        "db_qps": 420.0,
        "queue_depth": 380.0,
        "request_fanout": 14.0,
    },
    initial_traces=[
        "GET /search -> search_controller -> db.query",
    ],
    hidden_traces=[
        "GET /search -> result_expansion -> db.query x12",
        "worker wait time elevated before request execution",
    ],
    recent_deploys=[
        "deploy_3310: enable expanded-results feature flag",
        "deploy_3311: lower worker concurrency for cost optimization",
    ],
    config_snapshot={
        "EXPANDED_RESULTS_ENABLED": "true",
        "SEARCH_WORKER_CONCURRENCY": "2",
        "DB_POOL_SIZE": "20",
    },
    code_snippet=(
        "def expand_results(items: list[str], db) -> list[dict]:\n"
        "    results = []\n"
        "    for item in items:\n"
        "        results.append(db.fetch_details(item))\n"
        "    return results\n"
    ),
    available_dashboards=[
        "search-latency",
        "worker-capacity",
        "database-throughput",
        "feature-flags",
    ],
    root_cause_keywords=[
        "n+1 query",
        "feature flag",
        "expanded results",
        "low worker concurrency",
        "request amplification",
    ],
    valid_mitigations=[
        "disable feature flag and increase worker concurrency",
        "rollback expanded-results and raise concurrency",
        "batch queries and increase workers",
    ],
    partial_mitigations=[
        "scale service",
        "increase worker concurrency only",
        "rollback deploy only",
    ],
    harmful_actions=[
        "restart_service",
        "tune db blindly",
        "do nothing",
    ],
    expected_checks=[
        "latency_restored",
        "timeout_rate_reduced",
        "queue_depth_normalized",
        "root_cause_identified",
        "safe_monitoring_added",
    ],
    max_steps=12,
    baseline_reliability=30.0,
)
