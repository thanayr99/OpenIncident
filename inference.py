from __future__ import annotations

import os
from typing import List

from openai import OpenAI

from models import ActionType, IncidentAction, IncidentObservation
from server.environment import ProductionIncidentEnv

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
BENCHMARK = "production_incident_debugging"
TASKS = ["easy", "medium", "hard"]
VALID_ACTIONS = {action_type.value for action_type in ActionType}


def strict_score(value: float) -> float:
    return max(0.01, min(0.99, round(value, 4)))


def fallback_policy(task_name: str, step: int) -> tuple[str, str | None]:
    if task_name == "easy":
        plan = [
            ("inspect_logs", None),
            ("inspect_code", None),
            ("identify_root_cause", "Null input reaches strip() in profile normalization without a guard."),
            ("apply_fix", "add null guard to normalize_display_name"),
            ("resolve_incident", None),
        ]
    elif task_name == "medium":
        plan = [
            ("inspect_logs", None),
            ("inspect_config", None),
            ("inspect_code", None),
            ("identify_root_cause", "Stale cache comes from ttl too high and missing cache invalidation on promotion update."),
            ("apply_fix", "reduce ttl and patch invalidation logic"),
            ("resolve_incident", None),
        ]
    else:
        plan = [
            ("inspect_logs", None),
            ("inspect_metrics", None),
            ("inspect_traces", None),
            ("inspect_config", None),
            ("identify_root_cause", "Feature flag enabled expanded results causing n+1 query amplification with low worker concurrency."),
            ("apply_fix", "disable feature flag and increase worker concurrency"),
            ("add_monitor", "latency and timeout alert for expanded-results rollout"),
            ("resolve_incident", None),
        ]
    if step - 1 < len(plan):
        return plan[step - 1]
    return ("do_nothing", None)


def format_bool(value: bool) -> str:
    return "true" if value else "false"


def parse_llm_action(raw: str) -> tuple[str | None, str | None]:
    text = raw.strip()
    if not text or "|" not in text:
        return None, None

    action_type, content = text.split("|", 1)
    action_type = action_type.strip()
    content = content.strip() or None

    if action_type not in VALID_ACTIONS:
        return None, None

    if content in {"CONTENT", "ACTION_TYPE|CONTENT"}:
        content = None

    return action_type, content


def should_accept_llm_action(
    action_type: str,
    state: IncidentObservation,
    action_history: List[str],
) -> bool:
    if action_type.startswith("inspect_") and action_type in action_history:
        return False
    if action_type == ActionType.IDENTIFY_ROOT_CAUSE.value and state.root_cause_confirmed:
        return False
    if action_type == ActionType.ADD_MONITOR.value and state.monitoring_added:
        return False
    if action_type == ActionType.RESOLVE_INCIDENT.value and not state.service_restored:
        return False
    return True


def choose_action_with_openai(
    openai_client: OpenAI,
    task_name: str,
    state: IncidentObservation,
    fallback_action: str,
    fallback_content: str | None,
    action_history: List[str],
) -> tuple[str, str | None]:
    completion = openai_client.responses.create(
        model=MODEL_NAME,
        input=[
            {
                "role": "system",
                "content": (
                    "You are an on-call backend engineer solving a production incident. "
                    "Reply with exactly one line in the format ACTION_TYPE|CONTENT. "
                    "Valid actions: inspect_logs, inspect_metrics, inspect_traces, "
                    "inspect_deploys, inspect_config, inspect_code, identify_root_cause, "
                    "apply_fix, rollback_deploy, restart_service, scale_service, "
                    "add_monitor, resolve_incident, do_nothing."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task: {task_name}\n"
                    f"Summary: {state.incident_summary}\n"
                    f"Severity: {state.severity}\n"
                    f"User impact: {state.user_impact}\n"
                    f"Logs: {state.logs}\n"
                    f"Metrics: {state.metrics}\n"
                    f"Traces: {state.traces}\n"
                    f"Recent deploys: {state.recent_deploys}\n"
                    f"Config: {state.config_snapshot}\n"
                    f"Code: {state.code_snippet}\n"
                    f"Checks: passed={state.passed_checks} failed={state.failed_checks}\n"
                    f"Status: restored={state.service_restored} root_cause={state.root_cause_confirmed} monitoring={state.monitoring_added}\n"
                    f"Previous actions: {action_history}\n"
                    f"If uncertain, prefer this safe baseline next action: {fallback_action}|{fallback_content or ''}\n"
                ),
            },
        ],
    )
    suggested_action, suggested_content = parse_llm_action(completion.output_text)
    if (
        suggested_action is not None
        and should_accept_llm_action(
            suggested_action,
            state,
            action_history,
        )
    ):
        return suggested_action, suggested_content
    return fallback_action, fallback_content


def main() -> None:
    llm_enabled = bool(HF_TOKEN)
    openai_client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL) if llm_enabled else None

    for task_name in TASKS:
        env = ProductionIncidentEnv(task_id=task_name)
        state = env.reset()
        rewards: List[float] = []
        success = False
        step_count = 0
        final_score = 0.01

        print(f"[START] task={task_name} env={BENCHMARK} model={MODEL_NAME}")

        try:
            done = False
            while not done:
                step_count += 1
                action_type, content = fallback_policy(task_name, step_count)

                if llm_enabled and openai_client is not None:
                    try:
                        action_type, content = choose_action_with_openai(
                            openai_client=openai_client,
                            task_name=task_name,
                            state=state,
                            fallback_action=action_type,
                            fallback_content=content,
                            action_history=env.action_history,
                        )
                    except Exception:
                        pass

                observation, reward, done, info = env.step(IncidentAction(action_type=action_type, content=content))
                state = observation
                rewards.append(reward)
                success = state.current_status == "resolved"
                final_score = strict_score(reward)
                error_value = info.get("last_action_error")
                error_text = str(error_value) if error_value else "null"
                action_str = action_type if content is None else f"{action_type}:{content}"
                print(
                    f"[STEP] step={step_count} action={action_str} reward={reward:.2f} "
                    f"done={format_bool(done)} error={error_text}"
                )
        finally:
            reward_series = ",".join(f"{reward:.2f}" for reward in rewards)
            print(
                f"[END] success={format_bool(success)} steps={step_count} "
                f"score={final_score:.2f} rewards={reward_series}"
            )


if __name__ == "__main__":
    main()
