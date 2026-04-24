from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from models import (
    AgentRole,
    ApiTrainingRecord,
    FrontendStoryTestPlan,
    FrontendTrainingRecord,
    PlannerDecisionRecord,
    ProjectApiTrainingDataset,
    PlannerDomainBreakdown,
    ProjectBrowserCheckRequest,
    ProjectConfig,
    ProjectFrontendTrainingDataset,
    ProjectPlannerSummary,
    ProjectPlannerTrainingDataset,
    ProjectValidationSnapshot,
    StoryDomain,
    StoryExecutionPriority,
    StoryStatus,
    StoryTestType,
    UserStoryAnalysis,
    UserStoryExecutionResult,
    UserStoryRecord,
)
from server.browser_checks import run_http_browser_check, run_playwright_browser_check
from server.github_repo import build_frontend_story_plan


DOMAIN_KEYWORDS: dict[StoryDomain, tuple[str, ...]] = {
    StoryDomain.FRONTEND: ("page", "screen", "button", "form", "ui", "frontend", "render", "visible"),
    StoryDomain.API: ("api", "endpoint", "request", "response", "status code", "json", "route"),
    StoryDomain.DATABASE: ("database", "db", "table", "record", "store", "save", "persist", "query"),
    StoryDomain.AUTH: ("login", "register", "sign in", "sign up", "token", "session", "password", "auth"),
    StoryDomain.INTEGRATION: ("webhook", "sync", "integration", "third-party", "notification", "email notification"),
    StoryDomain.PERFORMANCE: ("latency", "slow", "performance", "load", "throughput", "timeout"),
    StoryDomain.DEPLOYMENT: ("deploy", "release", "rollback", "environment", "config", "version"),
}

FIELD_WEIGHTS = {
    "title": 3.0,
    "description": 2.0,
    "acceptance_criteria": 2.5,
    "tags": 1.5,
}


def _story_text(story: UserStoryRecord) -> str:
    parts = [story.title, story.description, *story.acceptance_criteria, *story.tags]
    return " ".join(part for part in parts if part).lower()


def _collect_story_fields(story: UserStoryRecord) -> dict[str, str]:
    return {
        "title": story.title.lower(),
        "description": story.description.lower(),
        "acceptance_criteria": " ".join(item.lower() for item in story.acceptance_criteria),
        "tags": " ".join(item.lower() for item in story.tags),
    }

def score_story_domains(story: UserStoryRecord) -> dict[StoryDomain, float]:
    fields = _collect_story_fields(story)
    scores: dict[StoryDomain, float] = defaultdict(float)

    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            pattern = rf"\b{re.escape(keyword)}\b"
            for field_name, field_text in fields.items():
                if re.search(pattern, field_text):
                    scores[domain] += FIELD_WEIGHTS[field_name]

    hints = story.hints
    if hints.path or hints.expected_text or hints.expected_selector:
        scores[StoryDomain.FRONTEND] += 2.5
    if hints.api_path:
        scores[StoryDomain.API] += 3.0
    if hints.method and hints.method.upper() != "GET":
        scores[StoryDomain.API] += 1.0
    if hints.expected_status != 200:
        scores[StoryDomain.API] += 0.75

    text = _story_text(story)
    if any(word in text for word in ("login", "sign in", "sign up", "register", "password", "session", "token")):
        scores[StoryDomain.AUTH] += 2.25
    if any(word in text for word in ("slow", "latency", "timeout", "throughput", "performance")):
        scores[StoryDomain.PERFORMANCE] += 1.5
    if any(word in text for word in ("deploy", "release", "rollback", "branch", "environment", "vercel")):
        scores[StoryDomain.DEPLOYMENT] += 1.5

    if not scores:
        scores[StoryDomain.UNKNOWN] = 1.0
    return dict(scores)


def infer_story_domains(story: UserStoryRecord) -> list[StoryDomain]:
    scores = score_story_domains(story)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0].value))
    matched = [domain for domain, score in ordered if score > 0]
    return matched or [StoryDomain.UNKNOWN]


def choose_primary_domain(domains: Iterable[StoryDomain], domain_scores: dict[StoryDomain, float] | None = None) -> StoryDomain:
    ordered = list(domains)
    if domain_scores:
        ordered = [item[0] for item in sorted(domain_scores.items(), key=lambda item: (-item[1], item[0].value))]
    if StoryDomain.AUTH in ordered and StoryDomain.FRONTEND in ordered:
        return StoryDomain.AUTH
    if StoryDomain.AUTH in ordered and StoryDomain.API in ordered:
        return StoryDomain.AUTH
    if StoryDomain.API in ordered:
        return StoryDomain.API
    if StoryDomain.FRONTEND in ordered:
        return StoryDomain.FRONTEND
    if StoryDomain.DATABASE in ordered:
        return StoryDomain.DATABASE
    if StoryDomain.INTEGRATION in ordered:
        return StoryDomain.INTEGRATION
    if StoryDomain.PERFORMANCE in ordered:
        return StoryDomain.PERFORMANCE
    if StoryDomain.DEPLOYMENT in ordered:
        return StoryDomain.DEPLOYMENT
    return ordered[0] if ordered else StoryDomain.UNKNOWN


def suggest_test_types(domains: list[StoryDomain]) -> list[StoryTestType]:
    suggested: list[StoryTestType] = []
    if StoryDomain.FRONTEND in domains or StoryDomain.AUTH in domains:
        suggested.append(StoryTestType.BROWSER)
    if StoryDomain.API in domains or StoryDomain.INTEGRATION in domains:
        suggested.append(StoryTestType.API)
    if StoryDomain.DATABASE in domains:
        suggested.append(StoryTestType.DATABASE)
    if StoryDomain.PERFORMANCE in domains:
        suggested.append(StoryTestType.HEALTH)
    if StoryDomain.DEPLOYMENT in domains:
        suggested.append(StoryTestType.CODE_REVIEW)
    if not suggested:
        suggested.append(StoryTestType.MANUAL_REVIEW)
    return suggested


def normalize_domain_scores(scores: dict[StoryDomain, float]) -> dict[str, float]:
    total = sum(scores.values())
    if total <= 0:
        return {StoryDomain.UNKNOWN.value: 1.0}
    return {
        domain.value: round(score / total, 4)
        for domain, score in sorted(scores.items(), key=lambda item: (-item[1], item[0].value))
    }


def infer_execution_priority(story: UserStoryRecord, domains: list[StoryDomain], scores: dict[StoryDomain, float]) -> StoryExecutionPriority:
    text = _story_text(story)
    if StoryDomain.AUTH in domains or StoryDomain.DEPLOYMENT in domains:
        return StoryExecutionPriority.HIGH
    if StoryDomain.PERFORMANCE in domains:
        return StoryExecutionPriority.HIGH
    if story.hints.expected_status >= 500 or any(word in text for word in ("critical", "urgent", "payment", "checkout", "production")):
        return StoryExecutionPriority.CRITICAL
    if StoryDomain.API in domains or StoryDomain.FRONTEND in domains or max(scores.values(), default=0.0) >= 4.5:
        return StoryExecutionPriority.HIGH
    if StoryDomain.UNKNOWN in domains:
        return StoryExecutionPriority.MEDIUM
    return StoryExecutionPriority.MEDIUM


def infer_planning_notes(story: UserStoryRecord, domains: list[StoryDomain], primary_domain: StoryDomain) -> list[str]:
    notes: list[str] = []
    if len(domains) > 1 and StoryDomain.UNKNOWN not in domains:
        notes.append("This story spans multiple domains and may need staged validation.")
    if primary_domain in {StoryDomain.FRONTEND, StoryDomain.AUTH} and not (story.hints.expected_text or story.hints.expected_selector):
        notes.append("Add expected_text or expected_selector for more reliable browser automation.")
    if primary_domain == StoryDomain.API and not story.hints.api_path:
        notes.append("Add hints.api_path for stronger endpoint targeting.")
    if primary_domain == StoryDomain.DATABASE:
        notes.append("Database execution is not fully automated yet, so this will likely need repository and evidence review.")
    if StoryDomain.DEPLOYMENT in domains:
        notes.append("Repository and test-environment context should be pulled before execution.")
    return notes


def compute_analysis_confidence(scores: dict[StoryDomain, float]) -> float:
    ordered = sorted(scores.values(), reverse=True)
    if not ordered:
        return 0.0
    top = ordered[0]
    runner_up = ordered[1] if len(ordered) > 1 else 0.0
    confidence = 0.45 + min(top / 8.0, 0.35) + min(max(top - runner_up, 0.0) / 6.0, 0.2)
    return round(min(0.99, confidence), 4)


def assign_agent(primary_domain: StoryDomain) -> AgentRole:
    mapping = {
        StoryDomain.FRONTEND: AgentRole.FRONTEND_TESTER,
        StoryDomain.AUTH: AgentRole.FRONTEND_TESTER,
        StoryDomain.API: AgentRole.API_TESTER,
        StoryDomain.DATABASE: AgentRole.DATABASE_ANALYST,
        StoryDomain.INTEGRATION: AgentRole.RELIABILITY_ANALYST,
        StoryDomain.PERFORMANCE: AgentRole.RELIABILITY_ANALYST,
        StoryDomain.DEPLOYMENT: AgentRole.TEST_ENV_GUARDIAN,
        StoryDomain.UNKNOWN: AgentRole.PLANNER,
    }
    return mapping[primary_domain]


def analyze_story(story: UserStoryRecord) -> UserStoryAnalysis:
    raw_scores = score_story_domains(story)
    domains = infer_story_domains(story)
    primary_domain = choose_primary_domain(domains, raw_scores)
    suggested = suggest_test_types(domains)
    priority = infer_execution_priority(story, domains, raw_scores)
    planning_notes = infer_planning_notes(story, domains, primary_domain)
    normalized_scores = normalize_domain_scores(raw_scores)
    confidence = compute_analysis_confidence(raw_scores)
    top_domains = ", ".join(f"{domain} ({score:.0%})" for domain, score in list(normalized_scores.items())[:3])
    assigned_agent = assign_agent(primary_domain)
    reasoning = (
        f"The Planner scored this story against multiple domains and found the strongest match in "
        f"{primary_domain.value}. Top signals: {top_domains}. "
        f"It is routed to {assigned_agent.value} with suggested validations "
        f"{', '.join(test.value for test in suggested)} and priority {priority.value}."
    )
    return UserStoryAnalysis(
        primary_domain=primary_domain,
        domains=domains,
        assigned_agent=assigned_agent,
        suggested_test_types=suggested,
        domain_scores=normalized_scores,
        confidence_score=confidence,
        execution_priority=priority,
        planning_notes=planning_notes,
        needs_repository_context=primary_domain in {StoryDomain.DATABASE, StoryDomain.DEPLOYMENT, StoryDomain.INTEGRATION},
        needs_runtime_validation=primary_domain != StoryDomain.UNKNOWN,
        reasoning=reasoning,
    )


def infer_story_path(story: UserStoryRecord) -> str | None:
    if story.hints.path:
        return story.hints.path
    if story.hints.api_path:
        return story.hints.api_path
    text = " ".join([story.title, story.description, *story.acceptance_criteria])
    match = re.search(r"(/[A-Za-z0-9_\-/]+)", text)
    if match:
        return match.group(1)
    return None


def build_story_report(project_id: str, stories: list[UserStoryRecord]):
    total = len(stories)
    completed = sum(story.status == StoryStatus.COMPLETED for story in stories)
    failed = sum(story.status == StoryStatus.FAILED for story in stories)
    blocked = sum(story.status == StoryStatus.BLOCKED for story in stories)
    pending = sum(story.status in {StoryStatus.PENDING, StoryStatus.ANALYZED, StoryStatus.RUNNING} for story in stories)
    progress = round((completed / total) * 100, 2) if total else 0.0
    from models import ProjectStoryReport

    return ProjectStoryReport(
        project_id=project_id,
        total_stories=total,
        completed_stories=completed,
        failed_stories=failed,
        blocked_stories=blocked,
        pending_stories=pending,
        progress_percent=progress,
        stories=stories,
    )


def build_planner_summary(project_id: str, stories: list[UserStoryRecord]) -> ProjectPlannerSummary:
    analyzed_stories = [story for story in stories if story.analysis is not None]
    domain_groups: dict[StoryDomain, list[UserStoryRecord]] = defaultdict(list)
    for story in analyzed_stories:
        domain_groups[story.analysis.primary_domain].append(story)

    def _priority_rank(story: UserStoryRecord) -> int:
        priority = story.analysis.execution_priority if story.analysis else StoryExecutionPriority.MEDIUM
        return {
            StoryExecutionPriority.CRITICAL: 0,
            StoryExecutionPriority.HIGH: 1,
            StoryExecutionPriority.MEDIUM: 2,
            StoryExecutionPriority.LOW: 3,
        }[priority]

    prioritized = sorted(
        analyzed_stories,
        key=lambda story: (
            _priority_rank(story),
            -(story.analysis.confidence_score if story.analysis else 0.0),
            story.created_at,
        ),
    )

    breakdown = [
        PlannerDomainBreakdown(
            domain=domain,
            total_stories=len(group),
            assigned_agent=group[0].analysis.assigned_agent,
            suggested_test_types=group[0].analysis.suggested_test_types,
            high_priority_stories=sum(
                story.analysis.execution_priority in {StoryExecutionPriority.HIGH, StoryExecutionPriority.CRITICAL}
                for story in group
                if story.analysis is not None
            ),
        )
        for domain, group in sorted(domain_groups.items(), key=lambda item: (-len(item[1]), item[0].value))
    ]

    next_actions: list[str] = []
    if any(story.analysis and story.analysis.needs_repository_context for story in prioritized[:5]):
        next_actions.append("Pull repository workspace before executing repository-dependent stories.")
    if any(
        story.analysis and StoryTestType.BROWSER in story.analysis.suggested_test_types
        for story in prioritized[:5]
    ):
        next_actions.append("Run frontend discovery so browser-routed stories can infer routes and selectors.")
    if any(
        story.analysis and story.analysis.primary_domain == StoryDomain.API
        for story in prioritized[:5]
    ):
        next_actions.append("Validate API base paths and endpoint hints for the highest-priority API stories.")
    if not next_actions:
        next_actions.append("Analyze the remaining stories and keep executing the highest-priority planned work.")

    return ProjectPlannerSummary(
        project_id=project_id,
        total_stories=len(stories),
        analyzed_stories=len(analyzed_stories),
        unclassified_stories=sum(story.analysis is None for story in stories),
        domain_breakdown=breakdown,
        prioritized_story_ids=[story.story_id for story in prioritized],
        next_recommended_actions=next_actions,
        stories=prioritized,
    )


def build_planner_training_dataset(project_id: str, stories: list[UserStoryRecord]) -> ProjectPlannerTrainingDataset:
    records: list[PlannerDecisionRecord] = []
    matched_count = 0
    matched_total = 0

    for story in sorted(stories, key=lambda item: item.created_at):
        if story.analysis is None:
            continue

        latest_result = story.latest_result
        final_status = latest_result.status if latest_result else story.status
        executed_test_type = latest_result.test_type if latest_result else None
        execution_success = latest_result.success if latest_result else None
        outcome_label = (
            "passed"
            if execution_success is True
            else "failed"
            if execution_success is False and final_status == StoryStatus.FAILED
            else "blocked"
            if final_status == StoryStatus.BLOCKED
            else "pending"
        )

        matched_assigned_agent = None
        if executed_test_type is not None:
            expected_test_types = set(story.analysis.suggested_test_types)
            matched_assigned_agent = executed_test_type in expected_test_types
            matched_total += 1
            matched_count += int(matched_assigned_agent)

        records.append(
            PlannerDecisionRecord(
                story_id=story.story_id,
                project_id=story.project_id,
                title=story.title,
                created_at=story.created_at,
                primary_domain=story.analysis.primary_domain,
                assigned_agent=story.analysis.assigned_agent,
                execution_priority=story.analysis.execution_priority,
                confidence_score=story.analysis.confidence_score,
                suggested_test_types=story.analysis.suggested_test_types,
                needs_repository_context=story.analysis.needs_repository_context,
                needs_runtime_validation=story.analysis.needs_runtime_validation,
                planning_notes=story.analysis.planning_notes,
                domain_scores=story.analysis.domain_scores,
                final_status=final_status,
                executed_test_type=executed_test_type,
                execution_success=execution_success,
                linked_run_id=latest_result.linked_run_id if latest_result else None,
                linked_session_id=latest_result.linked_session_id if latest_result else None,
                outcome_label=outcome_label,
                matched_assigned_agent=matched_assigned_agent,
            )
        )

    completed_records = sum(record.final_status == StoryStatus.COMPLETED for record in records)
    failed_records = sum(record.final_status == StoryStatus.FAILED for record in records)
    blocked_records = sum(record.final_status == StoryStatus.BLOCKED for record in records)
    pending_records = len(records) - completed_records - failed_records - blocked_records

    return ProjectPlannerTrainingDataset(
        project_id=project_id,
        total_records=len(stories),
        analyzed_records=len(records),
        completed_records=completed_records,
        failed_records=failed_records,
        blocked_records=blocked_records,
        pending_records=pending_records,
        route_match_rate=round(matched_count / matched_total, 4) if matched_total else 0.0,
        records=records,
    )


def build_frontend_training_dataset(
    project: ProjectConfig,
    stories: list[UserStoryRecord],
    workspace_path: str | None = None,
) -> ProjectFrontendTrainingDataset:
    candidate_stories = [
        story
        for story in stories
        if story.analysis is not None
        and (
            story.analysis.assigned_agent == AgentRole.FRONTEND_TESTER
            or story.analysis.primary_domain in {StoryDomain.FRONTEND, StoryDomain.AUTH}
        )
    ]

    records: list[FrontendTrainingRecord] = []
    route_hint_checks = 0
    route_hint_matches = 0
    expected_text_count = 0
    selector_count = 0

    for story in sorted(candidate_stories, key=lambda item: item.created_at):
        latest_result = story.latest_result
        stored_plan_payload = latest_result.output.get("frontend_plan") if latest_result and latest_result.output else None
        plan = (
            FrontendStoryTestPlan.model_validate(stored_plan_payload)
            if stored_plan_payload
            else build_frontend_story_plan(project, story, workspace_path=workspace_path)
        )

        route_hint_match = None
        if story.hints.path and plan.inferred_route:
            route_hint_checks += 1
            route_hint_match = story.hints.path == plan.inferred_route
            route_hint_matches += int(route_hint_match)

        if plan.expected_text:
            expected_text_count += 1
        if plan.expected_selector:
            selector_count += 1

        final_status = latest_result.status if latest_result else story.status
        execution_success = latest_result.success if latest_result else None
        executed_target_url = latest_result.output.get("target_url") if latest_result and latest_result.output else None
        observed_url = latest_result.output.get("observed_url") if latest_result and latest_result.output else None
        page_title = latest_result.output.get("page_title") if latest_result and latest_result.output else None
        error_message = latest_result.output.get("error_message") if latest_result and latest_result.output else None

        outcome_label = (
            "passed"
            if execution_success is True
            else "failed"
            if execution_success is False and final_status == StoryStatus.FAILED
            else "blocked"
            if final_status == StoryStatus.BLOCKED
            else "pending"
        )

        records.append(
            FrontendTrainingRecord(
                story_id=story.story_id,
                project_id=story.project_id,
                title=story.title,
                created_at=story.created_at,
                primary_domain=story.analysis.primary_domain if story.analysis else None,
                assigned_agent=story.analysis.assigned_agent if story.analysis else None,
                inferred_route=plan.inferred_route,
                expected_text=plan.expected_text,
                expected_selector=plan.expected_selector,
                browser_mode=plan.browser_mode,
                reasoning=plan.reasoning,
                candidate_route_count=len(plan.candidate_routes),
                route_hint_match=route_hint_match,
                final_status=final_status,
                execution_success=execution_success,
                executed_target_url=executed_target_url,
                observed_url=observed_url,
                page_title=page_title,
                error_message=error_message,
                linked_run_id=latest_result.linked_run_id if latest_result else None,
                linked_session_id=latest_result.linked_session_id if latest_result else None,
                outcome_label=outcome_label,
            )
        )

    successful_records = sum(record.execution_success is True for record in records)
    failed_records = sum(record.final_status == StoryStatus.FAILED for record in records)
    blocked_records = sum(record.final_status == StoryStatus.BLOCKED for record in records)
    pending_records = len(records) - successful_records - failed_records - blocked_records

    return ProjectFrontendTrainingDataset(
        project_id=project.project_id,
        total_records=len(candidate_stories),
        planned_records=len(records),
        successful_records=successful_records,
        failed_records=failed_records,
        blocked_records=blocked_records,
        pending_records=pending_records,
        route_hint_match_rate=round(route_hint_matches / route_hint_checks, 4) if route_hint_checks else 0.0,
        expected_text_coverage_rate=round(expected_text_count / len(records), 4) if records else 0.0,
        selector_coverage_rate=round(selector_count / len(records), 4) if records else 0.0,
        records=records,
    )


def build_api_training_dataset(project_id: str, stories: list[UserStoryRecord]) -> ProjectApiTrainingDataset:
    candidate_stories = [
        story
        for story in stories
        if story.analysis is not None
        and (
            story.analysis.assigned_agent == AgentRole.API_TESTER
            or story.analysis.primary_domain == StoryDomain.API
        )
    ]

    records: list[ApiTrainingRecord] = []
    explicit_hint_count = 0
    status_match_checks = 0
    status_match_count = 0

    for story in sorted(candidate_stories, key=lambda item: item.created_at):
        latest_result = story.latest_result
        inferred_path = story.hints.api_path or infer_story_path(story)
        explicit_hint = bool(story.hints.api_path)
        explicit_hint_count += int(explicit_hint)

        actual_status = latest_result.output.get("status_code") if latest_result and latest_result.output else None
        response_time_ms = latest_result.output.get("response_time_ms") if latest_result and latest_result.output else None
        target_url = latest_result.output.get("target_url") if latest_result and latest_result.output else None
        response_excerpt = latest_result.output.get("response_excerpt") if latest_result and latest_result.output else None
        error_message = latest_result.output.get("error_message") if latest_result and latest_result.output else None

        status_match = None
        if actual_status is not None:
            status_match_checks += 1
            status_match = actual_status == story.hints.expected_status
            status_match_count += int(status_match)

        final_status = latest_result.status if latest_result else story.status
        execution_success = latest_result.success if latest_result else None
        outcome_label = (
            "passed"
            if execution_success is True
            else "failed"
            if execution_success is False and final_status == StoryStatus.FAILED
            else "blocked"
            if final_status == StoryStatus.BLOCKED
            else "pending"
        )

        records.append(
            ApiTrainingRecord(
                story_id=story.story_id,
                project_id=story.project_id,
                title=story.title,
                created_at=story.created_at,
                primary_domain=story.analysis.primary_domain if story.analysis else None,
                assigned_agent=story.analysis.assigned_agent if story.analysis else None,
                expected_method=story.hints.method.upper(),
                inferred_path=inferred_path,
                expected_status=story.hints.expected_status,
                has_explicit_api_hint=explicit_hint,
                reasoning=story.analysis.reasoning if story.analysis else "",
                final_status=final_status,
                execution_success=execution_success,
                actual_status=actual_status,
                response_time_ms=response_time_ms,
                target_url=target_url,
                response_excerpt=response_excerpt,
                error_message=error_message,
                linked_run_id=latest_result.linked_run_id if latest_result else None,
                linked_session_id=latest_result.linked_session_id if latest_result else None,
                outcome_label=outcome_label,
                status_match=status_match,
            )
        )

    successful_records = sum(record.execution_success is True for record in records)
    failed_records = sum(record.final_status == StoryStatus.FAILED for record in records)
    blocked_records = sum(record.final_status == StoryStatus.BLOCKED for record in records)
    pending_records = len(records) - successful_records - failed_records - blocked_records

    return ProjectApiTrainingDataset(
        project_id=project_id,
        total_records=len(candidate_stories),
        planned_records=len(records),
        successful_records=successful_records,
        failed_records=failed_records,
        blocked_records=blocked_records,
        pending_records=pending_records,
        explicit_hint_rate=round(explicit_hint_count / len(records), 4) if records else 0.0,
        status_match_rate=round(status_match_count / status_match_checks, 4) if status_match_checks else 0.0,
        records=records,
    )


def execute_frontend_story(
    story: UserStoryRecord,
    base_url: str,
    project=None,
    workspace_path: str | None = None,
) -> UserStoryExecutionResult:
    inferred_plan = (
        build_frontend_story_plan(project, story, workspace_path=workspace_path)
        if project and (project.repository_url or workspace_path)
        else None
    )
    path = story.hints.path or (inferred_plan.inferred_route if inferred_plan and inferred_plan.inferred_route else infer_story_path(story)) or "/"
    expected_text = story.hints.expected_text or (inferred_plan.expected_text if inferred_plan else None)
    if not expected_text:
        return UserStoryExecutionResult(
            story_id=story.story_id,
            project_id=story.project_id,
            status=StoryStatus.BLOCKED,
            test_type=StoryTestType.BROWSER,
            summary="The story was classified as frontend-focused, but no expected UI text could be inferred yet.",
            evidence=[
                "Add an expected_text, expected_selector, or clearer acceptance criteria to run this automatically."
            ],
        )

    request = ProjectBrowserCheckRequest(
        path=path,
        expected_text=expected_text,
        expected_selector=story.hints.expected_selector or (inferred_plan.expected_selector if inferred_plan else None),
        label=story.title,
        browser_mode="playwright",
        wait_until="networkidle",
    )
    target_url = f"{base_url.rstrip('/')}{path if path.startswith('/') else '/' + path}"
    result = run_playwright_browser_check(target_url, request)
    if result.get("status") == "tooling_error":
        result = run_http_browser_check(target_url, request)
        result["fallback_from"] = "playwright"
    status = StoryStatus.COMPLETED if result["status"] == "healthy" else StoryStatus.FAILED
    evidence = [
        f"Checked rendered page at {result.get('observed_url') or target_url}.",
        f"Page title: {result.get('page_title') or 'unknown'}.",
    ]
    if inferred_plan is not None:
        evidence.append(f"Auto frontend plan inferred route {path} from repository structure.")
    if result.get("error_message"):
        evidence.append(result["error_message"])
    if result.get("fallback_from"):
        evidence.append("Playwright was unavailable, so the frontend check used HTTP fallback mode.")
    output = dict(result)
    if inferred_plan is not None:
        output["frontend_plan"] = inferred_plan.model_dump(mode="json")
    return UserStoryExecutionResult(
        story_id=story.story_id,
        project_id=story.project_id,
        status=status,
        test_type=StoryTestType.BROWSER,
        success=status == StoryStatus.COMPLETED,
        summary="Frontend story passed browser validation." if status == StoryStatus.COMPLETED else "Frontend story failed browser validation.",
        evidence=evidence,
        output=output,
    )


def execute_api_story(story: UserStoryRecord, base_url: str) -> UserStoryExecutionResult:
    import requests
    from time import perf_counter

    path = story.hints.api_path or infer_story_path(story)
    if not path:
        return UserStoryExecutionResult(
            story_id=story.story_id,
            project_id=story.project_id,
            status=StoryStatus.BLOCKED,
            test_type=StoryTestType.API,
            summary="The story was classified as API-focused, but no API path could be inferred.",
            evidence=["Add hints.api_path or include a clear endpoint path in the story."],
        )

    target_url = f"{base_url.rstrip('/')}{path if path.startswith('/') else '/' + path}"
    started_at = perf_counter()
    try:
        response = requests.request(story.hints.method.upper(), target_url, timeout=10)
        response_time_ms = round((perf_counter() - started_at) * 1000, 2)
        success = response.status_code == story.hints.expected_status
        snapshot = ProjectValidationSnapshot(
            project_id=story.project_id,
            check_type="api",
            label=story.title,
            target_url=target_url,
            status="healthy" if success else "unhealthy",
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            error_message=None if success else f"Expected {story.hints.expected_status}, got {response.status_code}",
            response_excerpt=response.text[:300] if response.text else None,
            engine="requests",
            observed_url=target_url,
        )
        return UserStoryExecutionResult(
            story_id=story.story_id,
            project_id=story.project_id,
            status=StoryStatus.COMPLETED if success else StoryStatus.FAILED,
            test_type=StoryTestType.API,
            success=success,
            summary="API story passed endpoint validation." if success else "API story failed endpoint validation.",
            evidence=[
                f"Called {story.hints.method.upper()} {target_url}.",
                f"Received status {response.status_code} in {response_time_ms} ms.",
            ],
            output=snapshot.model_dump(mode="json"),
        )
    except requests.RequestException as exc:
        return UserStoryExecutionResult(
            story_id=story.story_id,
            project_id=story.project_id,
            status=StoryStatus.FAILED,
            test_type=StoryTestType.API,
            success=False,
            summary="API story failed because the endpoint could not be reached.",
            evidence=[str(exc)],
            output={"target_url": target_url},
        )
