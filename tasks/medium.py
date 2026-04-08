from models import IncidentTask


TASK_MEDIUM = IncidentTask(
    task_id="medium",
    difficulty="medium",
    title="Stale Checkout Pricing Incident",
    service_name="checkout-service",
    incident_summary="Customers see stale discounted prices after promotion updates.",
    severity="high",
    user_impact="Incorrect totals at checkout for a subset of users.",
    initial_logs=[
        "WARN checkout total mismatch for cart_id=7782",
        "INFO cache hit key=price:sku-445",
    ],
    hidden_logs=[
        "INFO promotion update received but cache invalidation skipped",
    ],
    initial_metrics={
        "checkout_mismatch_rate": 6.8,
        "error_rate": 1.2,
        "p95_latency_ms": 180.0,
    },
    hidden_metrics={
        "cache_hit_rate": 97.5,
        "stale_price_rate": 8.1,
    },
    initial_traces=[
        "POST /checkout -> load_cached_price -> compute_total",
    ],
    hidden_traces=[
        "span=promotion_invalidation skipped=true reason=missing edge case match",
    ],
    recent_deploys=[
        "deploy_2201: update cache TTL defaults",
        "deploy_2202: promo engine edge-case cleanup",
    ],
    config_snapshot={
        "PRICE_CACHE_TTL": "3600",
        "CHECKOUT_REGION": "us-east-1",
    },
    code_snippet=(
        "def should_invalidate_price_cache(event_type: str, promo_id: str | None) -> bool:\n"
        "    if event_type == 'promotion_deleted':\n"
        "        return True\n"
        "    return False\n"
    ),
    available_dashboards=[
        "checkout-correctness",
        "cache-health",
        "promo-events",
    ],
    root_cause_keywords=[
        "ttl too high",
        "stale cache",
        "missing invalidation",
        "promotion update",
        "cache invalidation logic",
    ],
    valid_mitigations=[
        "reduce ttl and patch invalidation logic",
        "restore ttl and invalidate on promotion update",
        "clear cache and fix invalidation",
    ],
    partial_mitigations=[
        "rollback deploy",
        "clear cache only",
    ],
    harmful_actions=[
        "restart_service",
        "scale_service",
    ],
    expected_checks=[
        "pricing_correctness_restored",
        "cache_safety_restored",
        "root_cause_identified",
        "business_impact_reduced",
    ],
    max_steps=10,
    baseline_reliability=40.0,
)
