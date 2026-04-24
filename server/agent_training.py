from __future__ import annotations

from models import AgentTrainingPlan, AgentTrainingProfile, AgentTrainingStrategy


def build_agent_training_plan() -> AgentTrainingPlan:
    profiles = [
        AgentTrainingProfile(
            agent_id="planner_agent",
            display_name="Planner Agent",
            mapped_roles=["planner"],
            recommended_strategy=AgentTrainingStrategy.HYBRID,
            trainable_now=False,
            primary_environment="offline story-routing dataset",
            current_state="Rule-guided routing, prioritization, and planner-summary generation are in production.",
            why_this_strategy=(
                "Planner quality depends more on correct decomposition, routing accuracy, and handoff quality than on "
                "trial-and-error action rewards. It should learn first from labeled stories, execution outcomes, and "
                "operator corrections."
            ),
            required_data=[
                "stories and formal test cases",
                "assigned domains and agents",
                "execution outcomes by story",
                "human corrections to planner routing",
            ],
            next_milestone="Record planner decisions and downstream outcomes so we can build an offline routing dataset.",
        ),
        AgentTrainingProfile(
            agent_id="environment_agent",
            display_name="Environment Agent",
            mapped_roles=["conceptual:environment_agent", "test_env_guardian"],
            recommended_strategy=AgentTrainingStrategy.HEURISTIC_TOOLING,
            trainable_now=False,
            primary_environment="repository/workspace inspection",
            current_state="Framework detection, route discovery, and workspace summary are now implemented as deterministic tooling.",
            why_this_strategy=(
                "This agent is mostly about filesystem inspection, command inference, and connector reliability. Better "
                "tooling and fixture coverage will outperform RL here."
            ),
            required_data=[
                "repository fixtures across frameworks",
                "workspace pull outcomes",
                "framework detection test cases",
                "command inference validation cases",
            ],
            next_milestone="Expand fixture-based repository coverage for Next.js, Vite, Python, and mixed-stack repos.",
        ),
        AgentTrainingProfile(
            agent_id="frontend_test_agent",
            display_name="Frontend Test Agent",
            mapped_roles=["frontend_tester"],
            recommended_strategy=AgentTrainingStrategy.SUPERVISED_EVAL,
            trainable_now=False,
            primary_environment="browser execution traces + expected UI outcomes",
            current_state="The agent can already execute browser-style checks, but selector/path inference still relies on heuristics.",
            why_this_strategy=(
                "Frontend validation needs strong grounding in selectors, routes, expected text, and screenshots. Supervised "
                "evaluation on real UI cases is a better first step than RL."
            ),
            required_data=[
                "frontend user stories",
                "expected selectors and visible text",
                "Playwright pass/fail traces",
                "screenshots and console output",
            ],
            next_milestone="Collect executed frontend stories with inferred route, selector, expected text, and final outcome.",
        ),
        AgentTrainingProfile(
            agent_id="api_test_agent",
            display_name="API Test Agent",
            mapped_roles=["api_tester"],
            recommended_strategy=AgentTrainingStrategy.SUPERVISED_EVAL,
            trainable_now=False,
            primary_environment="HTTP/API contract evaluation",
            current_state="Endpoint smoke execution exists, but richer contract reasoning is still heuristic.",
            why_this_strategy=(
                "API testing is mostly about mapping requirements to endpoints, methods, payloads, auth, and expected statuses. "
                "That is better trained from labeled request/response examples and evaluation datasets."
            ),
            required_data=[
                "API stories and test cases",
                "expected methods/status codes/payloads",
                "auth variants",
                "real endpoint execution results",
            ],
            next_milestone="Store structured API execution traces so misclassification and false negatives can be analyzed.",
        ),
        AgentTrainingProfile(
            agent_id="database_agent",
            display_name="Database Agent",
            mapped_roles=["database_analyst"],
            recommended_strategy=AgentTrainingStrategy.HYBRID,
            trainable_now=False,
            primary_environment="schema/data reasoning + repository/database fixtures",
            current_state="The database agent is mostly a reasoning placeholder today with limited executable validation.",
            why_this_strategy=(
                "Database work needs schema awareness, migration reasoning, and data consistency checks. Start with fixtures, "
                "SQL-aware evaluation, and later add policy learning for remediation choices."
            ),
            required_data=[
                "schema snapshots",
                "migration scenarios",
                "data integrity bug examples",
                "database-related story outcomes",
            ],
            next_milestone="Add structured DB validation tasks before attempting policy learning.",
        ),
        AgentTrainingProfile(
            agent_id="observability_agent",
            display_name="Observability Agent",
            mapped_roles=["conceptual:observability_agent", "reliability_analyst"],
            recommended_strategy=AgentTrainingStrategy.HYBRID,
            trainable_now=False,
            primary_environment="logs/metrics/traces correlation tasks",
            current_state="Log ingestion and summarization exist, but deep evidence correlation is still shallow.",
            why_this_strategy=(
                "This agent needs both information extraction and ranking: which logs matter, which metrics correlate, and which "
                "signals should be handed to reliability or triage."
            ),
            required_data=[
                "log batches",
                "metric summaries",
                "trace excerpts",
                "incident root-cause labels",
            ],
            next_milestone="Persist evidence-to-root-cause mappings from incidents so correlation quality can be evaluated.",
        ),
        AgentTrainingProfile(
            agent_id="reliability_agent",
            display_name="Reliability Agent",
            mapped_roles=["reliability_analyst"],
            recommended_strategy=AgentTrainingStrategy.REINFORCEMENT_LEARNING,
            trainable_now=True,
            primary_environment="ProductionIncidentEnv",
            current_state="This is the first real RL target and already has a working epsilon-greedy + HF-compatible trainer.",
            why_this_strategy=(
                "Reliability decisions are sequential and reward-bearing: inspect, diagnose, mitigate, restore, and resolve. "
                "That makes it the strongest RL fit in the current system."
            ),
            required_data=[
                "incident trajectories",
                "action histories",
                "reward traces",
                "successful resolution sequences",
            ],
            next_milestone="Keep refining reward alignment and export trajectories for offline analysis and policy upgrades.",
        ),
        AgentTrainingProfile(
            agent_id="triage_agent",
            display_name="Triage Agent",
            mapped_roles=["conceptual:triage_agent", "reliability_analyst"],
            recommended_strategy=AgentTrainingStrategy.SUPERVISED_EVAL,
            trainable_now=False,
            primary_environment="incident-summary evaluation",
            current_state="Triage currently summarizes incidents from available evidence and confidence heuristics.",
            why_this_strategy=(
                "Triage quality is about explanation accuracy, evidence selection, and recommendation usefulness, which are "
                "better measured with scored summaries than with action rewards."
            ),
            required_data=[
                "incident evidence bundles",
                "golden triage summaries",
                "root-cause labels",
                "recommended remediation sets",
            ],
            next_milestone="Save triage inputs/outputs and allow operator rating so we can benchmark summary quality.",
        ),
        AgentTrainingProfile(
            agent_id="guardian_agent",
            display_name="Guardian Agent",
            mapped_roles=["test_env_guardian"],
            recommended_strategy=AgentTrainingStrategy.HYBRID,
            trainable_now=False,
            primary_environment="release gate decisions",
            current_state="Guardian already blocks based on checks, incidents, and validation status, but the policy is still simple.",
            why_this_strategy=(
                "Guardian is a decision gate. It should first learn from labeled release-ready vs blocked states, then later use "
                "policy tuning for borderline cases."
            ),
            required_data=[
                "predeploy runs",
                "story report outcomes",
                "incident status at release time",
                "human override decisions",
            ],
            next_milestone="Capture release-gate decisions with reasons and overrides so the gate can be calibrated.",
        ),
        AgentTrainingProfile(
            agent_id="oversight_agent",
            display_name="Oversight Agent",
            mapped_roles=["oversight"],
            recommended_strategy=AgentTrainingStrategy.SUPERVISED_EVAL,
            trainable_now=False,
            primary_environment="audit/review datasets",
            current_state="Oversight is still an audit layer built from heuristics and metadata rather than a learned reviewer.",
            why_this_strategy=(
                "Oversight should judge whether the other agents were reasonable, which is fundamentally an evaluation and ranking "
                "problem before it becomes a policy problem."
            ),
            required_data=[
                "agent decisions and traces",
                "final outcomes",
                "false-positive and false-negative examples",
                "operator audit notes",
            ],
            next_milestone="Build a review dataset of good vs bad agent decisions before trying to optimize audit behavior.",
        ),
    ]

    return AgentTrainingPlan(
        summary=(
            "Only the Reliability Agent is a true RL target right now. The remaining agents should first be hardened through "
            "tooling, labeled execution data, and supervised evaluation, then upgraded selectively into hybrid or RL systems."
        ),
        next_global_steps=[
            "Keep RL focused on the Reliability Agent until trajectory quality and reward alignment are stable.",
            "Start logging planner, frontend, API, triage, and guardian decisions with their downstream outcomes.",
            "Create offline evaluation datasets for routing, browser/API validation, triage quality, and release-gate decisions.",
            "Promote agents from heuristic to hybrid only after they have stable execution traces and measurable benchmarks.",
        ],
        profiles=profiles,
    )
