from __future__ import annotations

import argparse
import csv
import random
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from models import ActionType, IncidentAction, IncidentObservation, IncidentTask
from server.environment import ProductionIncidentEnv


@dataclass(frozen=True)
class ActionCandidate:
    """Serializable action candidate used by lightweight RL policies."""

    action_type: ActionType
    target: Optional[str] = None
    content: Optional[str] = None

    @property
    def key(self) -> str:
        parts = [self.action_type.value]
        if self.target:
            parts.append(f"target={self.target}")
        if self.content:
            parts.append(f"content={self.content}")
        return "|".join(parts)

    def to_incident_action(self) -> IncidentAction:
        return IncidentAction(action_type=self.action_type, target=self.target, content=self.content)


def extract_action_space(env: ProductionIncidentEnv) -> List[ActionCandidate]:
    """
    Build a minimal but valid action space from the existing environment/task.

    This deliberately derives action candidates from the current task definition
    so the trainer stays aligned with the codebase rather than introducing a
    parallel action model.
    """

    inspect_actions = [
        ActionCandidate(ActionType.INSPECT_LOGS),
        ActionCandidate(ActionType.INSPECT_METRICS),
        ActionCandidate(ActionType.INSPECT_TRACES),
        ActionCandidate(ActionType.INSPECT_DEPLOYS),
        ActionCandidate(ActionType.INSPECT_CONFIG),
        ActionCandidate(ActionType.INSPECT_CODE),
    ]

    root_cause_actions = [
        ActionCandidate(ActionType.IDENTIFY_ROOT_CAUSE, content=keyword)
        for keyword in env.task.root_cause_keywords
    ]
    mitigation_actions = [
        ActionCandidate(ActionType.APPLY_FIX, content=mitigation)
        for mitigation in (
            list(env.task.valid_mitigations)
            + list(env.task.partial_mitigations)
            + list(env.task.harmful_actions)
        )
    ]

    operational_actions = [
        ActionCandidate(ActionType.ROLLBACK_DEPLOY),
        ActionCandidate(ActionType.RESTART_SERVICE),
        ActionCandidate(ActionType.SCALE_SERVICE),
        ActionCandidate(ActionType.ADD_MONITOR),
        ActionCandidate(ActionType.RESOLVE_INCIDENT),
        ActionCandidate(ActionType.DO_NOTHING),
    ]

    action_candidates: List[ActionCandidate] = []
    seen: set[str] = set()
    for candidate in inspect_actions + root_cause_actions + mitigation_actions + operational_actions:
        if candidate.key in seen:
            continue
        seen.add(candidate.key)
        action_candidates.append(candidate)
    return action_candidates


@dataclass(frozen=True)
class StateFeatures:
    difficulty: str
    severity: str
    status: str
    step_phase: str
    reliability_band: str
    evidence_band: str
    log_band: str
    metric_band: str
    trace_band: str
    deploy_band: str
    checks_signature: str
    root_cause_confirmed: bool
    mitigation_applied: bool
    service_restored: bool
    monitoring_added: bool
    had_last_error: bool


def _bucketize_count(value: int) -> str:
    if value <= 0:
        return "none"
    if value == 1:
        return "one"
    if value <= 3:
        return "few"
    if value <= 8:
        return "some"
    return "many"


def _bucketize_reliability(value: float) -> str:
    if value < 25:
        return "critical"
    if value < 50:
        return "low"
    if value < 75:
        return "medium"
    return "high"


def _bucketize_step_phase(observation: IncidentObservation) -> str:
    if observation.max_steps <= 0:
        return "unknown"
    progress = observation.steps_taken / observation.max_steps
    if progress < 0.34:
        return "early"
    if progress < 0.67:
        return "mid"
    return "late"


def extract_state_features(observation: IncidentObservation) -> StateFeatures:
    evidence_points = int(bool(observation.logs)) + int(bool(observation.metrics)) + int(bool(observation.traces))
    evidence_points += int(bool(observation.recent_deploys)) + int(bool(observation.config_snapshot)) + int(bool(observation.code_snippet))
    return StateFeatures(
        difficulty=observation.difficulty,
        severity=observation.severity,
        status=observation.current_status,
        step_phase=_bucketize_step_phase(observation),
        reliability_band=_bucketize_reliability(observation.reliability_score),
        evidence_band=_bucketize_count(evidence_points),
        log_band=_bucketize_count(len(observation.logs)),
        metric_band=_bucketize_count(len(observation.metrics)),
        trace_band=_bucketize_count(len(observation.traces)),
        deploy_band=_bucketize_count(len(observation.recent_deploys)),
        checks_signature=f"{observation.passed_checks}:{observation.failed_checks}",
        root_cause_confirmed=observation.root_cause_confirmed,
        mitigation_applied=observation.mitigation_applied,
        service_restored=observation.service_restored,
        monitoring_added=observation.monitoring_added,
        had_last_error=bool(observation.last_action_error),
    )


def build_state_key(observation: IncidentObservation) -> str:
    """
    Compress the observation into a stable tabular-learning key.

    This is intentionally small and transparent so we can train a minimal
    epsilon-greedy baseline before introducing model-based policies.
    """

    features = extract_state_features(observation)
    return "|".join(
        [
            f"difficulty={features.difficulty}",
            f"severity={features.severity}",
            f"status={features.status}",
            f"phase={features.step_phase}",
            f"reliability={features.reliability_band}",
            f"evidence={features.evidence_band}",
            f"logs={features.log_band}",
            f"metrics={features.metric_band}",
            f"traces={features.trace_band}",
            f"deploys={features.deploy_band}",
            f"checks={features.checks_signature}",
            f"root={int(features.root_cause_confirmed)}",
            f"mitigated={int(features.mitigation_applied)}",
            f"restored={int(features.service_restored)}",
            f"monitor={int(features.monitoring_added)}",
            f"error={int(features.had_last_error)}",
        ]
    )


def render_state_summary(observation: IncidentObservation) -> str:
    features = extract_state_features(observation)
    return (
        f"incident={observation.incident_id}\n"
        f"title={observation.incident_summary}\n"
        f"service={observation.service_name}\n"
        f"difficulty={features.difficulty}\n"
        f"severity={features.severity}\n"
        f"status={features.status}\n"
        f"step_phase={features.step_phase}\n"
        f"reliability_band={features.reliability_band}\n"
        f"checks={features.checks_signature}\n"
        f"root_cause_confirmed={features.root_cause_confirmed}\n"
        f"mitigation_applied={features.mitigation_applied}\n"
        f"service_restored={features.service_restored}\n"
        f"monitoring_added={features.monitoring_added}\n"
        f"last_error={observation.last_action_error or 'none'}\n"
        f"log_count={len(observation.logs)}\n"
        f"metric_count={len(observation.metrics)}\n"
        f"trace_count={len(observation.traces)}\n"
        f"recent_deploys={len(observation.recent_deploys)}"
    )


class Policy(Protocol):
    def select_action(self, state: IncidentObservation, valid_actions: Sequence[ActionCandidate]) -> ActionCandidate:
        ...

    def observe(
        self,
        state: IncidentObservation,
        action: ActionCandidate,
        reward: float,
        next_state: IncidentObservation,
        done: bool,
    ) -> None:
        ...


@dataclass
class RandomPolicy:
    seed: Optional[int] = None
    _random: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)

    def select_action(self, state: IncidentObservation, valid_actions: Sequence[ActionCandidate]) -> ActionCandidate:
        del state
        return self._random.choice(list(valid_actions))

    def observe(
        self,
        state: IncidentObservation,
        action: ActionCandidate,
        reward: float,
        next_state: IncidentObservation,
        done: bool,
    ) -> None:
        del state, action, reward, next_state, done


@dataclass
class EpsilonGreedyPolicy:
    """
    Minimal tabular Q-learning policy with epsilon-greedy exploration.

    This keeps the first training layer intentionally lightweight while leaving
    a clear seam for a future HuggingFace-backed policy implementation.
    """

    epsilon: float = 0.30
    alpha: float = 0.35
    gamma: float = 0.92
    min_epsilon: float = 0.02
    epsilon_decay: float = 0.93
    guided_flow: bool = True
    prior_weight: float = 0.45
    warmup_episodes: int = 12
    seed: Optional[int] = None
    q_table: Dict[str, Dict[str, float]] = field(default_factory=dict)
    _random: random.Random = field(init=False, repr=False)
    _action_lookup: Dict[str, ActionCandidate] = field(default_factory=dict, init=False, repr=False)
    _episode_number: int = field(default=0, init=False, repr=False)
    _known_root_keywords: set[str] = field(default_factory=set, init=False, repr=False)
    _known_valid_mitigations: set[str] = field(default_factory=set, init=False, repr=False)
    _known_partial_mitigations: set[str] = field(default_factory=set, init=False, repr=False)
    _known_harmful_mitigations: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)

    def _normalize_phrase(self, phrase: str | None) -> str:
        return (phrase or "").strip().lower()

    def register_actions(self, actions: Iterable[ActionCandidate]) -> None:
        for action in actions:
            self._action_lookup[action.key] = action

    def begin_episode(self, task: IncidentTask, valid_actions: Sequence[ActionCandidate]) -> None:
        self._episode_number += 1
        self.register_actions(valid_actions)
        self._known_root_keywords = {self._normalize_phrase(keyword) for keyword in task.root_cause_keywords}
        self._known_valid_mitigations = {self._normalize_phrase(mitigation) for mitigation in task.valid_mitigations}
        self._known_partial_mitigations = {self._normalize_phrase(mitigation) for mitigation in task.partial_mitigations}
        self._known_harmful_mitigations = {self._normalize_phrase(mitigation) for mitigation in task.harmful_actions}

    def _ensure_state(self, state_key: str, valid_actions: Sequence[ActionCandidate]) -> None:
        action_values = self.q_table.setdefault(state_key, {})
        for action in valid_actions:
            self._action_lookup[action.key] = action
            action_values.setdefault(action.key, 0.0)

    def _is_inspect(self, action: ActionCandidate) -> bool:
        return action.action_type in {
            ActionType.INSPECT_LOGS,
            ActionType.INSPECT_METRICS,
            ActionType.INSPECT_TRACES,
            ActionType.INSPECT_DEPLOYS,
            ActionType.INSPECT_CONFIG,
            ActionType.INSPECT_CODE,
        }

    def _phase_actions(
        self,
        state: IncidentObservation,
        valid_actions: Sequence[ActionCandidate],
    ) -> List[ActionCandidate]:
        if not self.guided_flow:
            return list(valid_actions)

        visible_signals = int(bool(state.logs))
        visible_signals += int(bool(state.metrics))
        visible_signals += int(bool(state.traces))
        visible_signals += int(bool(state.recent_deploys))
        visible_signals += int(bool(state.config_snapshot))
        visible_signals += int(bool(state.code_snippet))

        if state.root_cause_confirmed and state.service_restored:
            phase = {ActionType.RESOLVE_INCIDENT, ActionType.ADD_MONITOR}
        elif state.current_status == "mitigation_pending_verification":
            phase = {
                ActionType.INSPECT_LOGS,
                ActionType.INSPECT_METRICS,
                ActionType.INSPECT_TRACES,
                ActionType.INSPECT_DEPLOYS,
            }
        elif not state.root_cause_confirmed and not state.service_restored:
            if visible_signals < 2:
                phase = {
                    ActionType.INSPECT_LOGS,
                    ActionType.INSPECT_METRICS,
                    ActionType.INSPECT_TRACES,
                    ActionType.INSPECT_DEPLOYS,
                    ActionType.INSPECT_CONFIG,
                    ActionType.INSPECT_CODE,
                }
            else:
                phase = {
                    ActionType.IDENTIFY_ROOT_CAUSE,
                    ActionType.INSPECT_LOGS,
                    ActionType.INSPECT_METRICS,
                    ActionType.INSPECT_TRACES,
                    ActionType.INSPECT_DEPLOYS,
                    ActionType.INSPECT_CONFIG,
                    ActionType.INSPECT_CODE,
                }
        elif state.root_cause_confirmed and not state.service_restored:
            phase = {
                ActionType.APPLY_FIX,
                ActionType.ROLLBACK_DEPLOY,
                ActionType.SCALE_SERVICE,
                ActionType.INSPECT_DEPLOYS,
                ActionType.INSPECT_CONFIG,
                ActionType.INSPECT_CODE,
            }
        else:
            phase = {
                ActionType.IDENTIFY_ROOT_CAUSE,
                ActionType.INSPECT_LOGS,
                ActionType.INSPECT_METRICS,
                ActionType.INSPECT_TRACES,
                ActionType.INSPECT_DEPLOYS,
                ActionType.INSPECT_CONFIG,
                ActionType.INSPECT_CODE,
            }

        filtered = [action for action in valid_actions if action.action_type in phase]
        return filtered or list(valid_actions)

    def _action_prior(self, state: IncidentObservation, action: ActionCandidate) -> float:
        normalized_content = self._normalize_phrase(action.content)
        recent_error = self._normalize_phrase(state.last_action_error)
        visible_signals = int(bool(state.logs))
        visible_signals += int(bool(state.metrics))
        visible_signals += int(bool(state.traces))
        visible_signals += int(bool(state.recent_deploys))
        visible_signals += int(bool(state.config_snapshot))
        visible_signals += int(bool(state.code_snippet))

        if action.action_type == ActionType.DO_NOTHING:
            return -2.0
        if action.action_type == ActionType.RESTART_SERVICE:
            return -1.8
        if action.action_type == ActionType.RESOLVE_INCIDENT:
            if state.root_cause_confirmed and state.service_restored:
                return 3.2
            if state.service_restored and not state.root_cause_confirmed:
                return -2.8
            return -3.2
        if action.action_type == ActionType.ADD_MONITOR:
            return 0.6 if (state.root_cause_confirmed or state.service_restored) else -0.7

        if not state.root_cause_confirmed and not state.service_restored:
            if ("evidence" in recent_error or "signal" in recent_error) and action.action_type == ActionType.IDENTIFY_ROOT_CAUSE:
                return -1.4
            if ("evidence" in recent_error or "signal" in recent_error) and self._is_inspect(action):
                return 2.8
            if action.action_type == ActionType.IDENTIFY_ROOT_CAUSE:
                if visible_signals < 2:
                    return 0.6
                return 2.6 if normalized_content in self._known_root_keywords else 1.8
            if self._is_inspect(action):
                return 2.1 if visible_signals < 2 else 1.0
            if action.action_type in {ActionType.APPLY_FIX, ActionType.ROLLBACK_DEPLOY, ActionType.SCALE_SERVICE}:
                return -0.9

        if state.root_cause_confirmed and not state.service_restored:
            if state.current_status == "mitigation_pending_verification":
                if self._is_inspect(action):
                    return 3.2
                if action.action_type == ActionType.APPLY_FIX:
                    return -1.4
                if action.action_type == ActionType.RESOLVE_INCIDENT:
                    return -2.8
            if action.action_type == ActionType.APPLY_FIX:
                if normalized_content in self._known_valid_mitigations:
                    return 2.8
                if normalized_content in self._known_partial_mitigations:
                    return 0.9
                if normalized_content in self._known_harmful_mitigations:
                    return -2.2
                return 0.2
            if action.action_type == ActionType.ROLLBACK_DEPLOY:
                return 0.7
            if action.action_type == ActionType.SCALE_SERVICE:
                return 0.4
            if self._is_inspect(action):
                return 0.3

        if state.service_restored and not state.root_cause_confirmed:
            if action.action_type == ActionType.IDENTIFY_ROOT_CAUSE:
                return 2.4
            if self._is_inspect(action):
                return 0.8

        return 0.0

    def _pick_greedy_action(
        self,
        state: IncidentObservation,
        state_key: str,
        candidate_actions: Sequence[ActionCandidate],
    ) -> ActionCandidate:
        action_values = self.q_table[state_key]
        scored: List[Tuple[ActionCandidate, float]] = []
        for action in candidate_actions:
            q_value = action_values[action.key]
            prior = self._action_prior(state, action)
            score = q_value + (self.prior_weight * prior)
            scored.append((action, score))

        best_score = max(score for _, score in scored)
        best_actions = [action for action, score in scored if score == best_score]
        return self._random.choice(best_actions)

    def select_action(self, state: IncidentObservation, valid_actions: Sequence[ActionCandidate]) -> ActionCandidate:
        state_key = build_state_key(state)
        candidate_actions = self._phase_actions(state, valid_actions)
        self._ensure_state(state_key, candidate_actions)

        if self._episode_number <= self.warmup_episodes and self.guided_flow:
            return self._pick_greedy_action(state, state_key, candidate_actions)

        if self._random.random() < self.epsilon:
            return self._random.choice(list(candidate_actions))

        return self._pick_greedy_action(state, state_key, candidate_actions)

    def observe(
        self,
        state: IncidentObservation,
        action: ActionCandidate,
        reward: float,
        next_state: IncidentObservation,
        done: bool,
    ) -> None:
        state_key = build_state_key(state)
        next_state_key = build_state_key(next_state)

        self._ensure_state(state_key, [action])
        if next_state_key not in self.q_table:
            next_candidates = list(self._action_lookup.values()) or [action]
            self._ensure_state(next_state_key, next_candidates)
        next_values = self.q_table.get(next_state_key, {})
        best_next = max(next_values.values(), default=0.0)
        current = self.q_table[state_key][action.key]
        target = reward if done else reward + (self.gamma * best_next)
        self.q_table[state_key][action.key] = current + self.alpha * (target - current)

    def decay(self) -> None:
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)


@dataclass
class HuggingFacePolicyAdapter:
    """
    Placeholder seam for a future model-backed policy.

    This allows later integration of a transformer policy without changing the
    episode runner or the environment contract.
    """

    model_name: str
    seed: Optional[int] = None
    max_new_tokens: int = 16
    temperature: float = 0.2
    _random: random.Random = field(init=False, repr=False)
    _generator: object | None = field(default=None, init=False, repr=False)
    _warning_emitted: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)

    def _load_generator(self) -> object:
        if self._generator is not None:
            return self._generator
        try:
            from transformers import pipeline  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "HuggingFace policy requires the 'transformers' package. "
                "Install it before using --policy hf."
            ) from exc
        self._generator = pipeline("text-generation", model=self.model_name)
        return self._generator

    def _build_prompt(self, state: IncidentObservation, valid_actions: Sequence[ActionCandidate]) -> str:
        action_lines = [
            f"{index}. {action.action_type.value}"
            + (f" | content={action.content}" if action.content else "")
            + (f" | target={action.target}" if action.target else "")
            for index, action in enumerate(valid_actions)
        ]
        return (
            "You are choosing the next incident-response action.\n"
            "Return only one integer index for the best next action.\n\n"
            f"State:\n{render_state_summary(state)}\n\n"
            "Available actions:\n"
            + "\n".join(action_lines)
            + "\n\nAnswer with only the integer index."
        )

    def _parse_index(self, text: str, num_actions: int) -> Optional[int]:
        digits = "".join(ch if ch.isdigit() else " " for ch in text).split()
        for token in digits:
            index = int(token)
            if 0 <= index < num_actions:
                return index
        return None

    def select_action(self, state: IncidentObservation, valid_actions: Sequence[ActionCandidate]) -> ActionCandidate:
        try:
            generator = self._load_generator()
            prompt = self._build_prompt(state, valid_actions)
            result = generator(  # type: ignore[operator]
                prompt,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                do_sample=self.temperature > 0,
            )
            generated_text = result[0]["generated_text"] if result else ""
            completion = generated_text[len(prompt) :] if generated_text.startswith(prompt) else generated_text
            index = self._parse_index(completion, len(valid_actions))
        except Exception as exc:
            if not self._warning_emitted:
                print(
                    f"HuggingFace policy fallback: could not use model '{self.model_name}' "
                    f"({exc}). Falling back to random valid actions."
                )
                self._warning_emitted = True
            index = None

        if index is None:
            return self._random.choice(list(valid_actions))
        return valid_actions[index]

    def observe(
        self,
        state: IncidentObservation,
        action: ActionCandidate,
        reward: float,
        next_state: IncidentObservation,
        done: bool,
    ) -> None:
        del state, action, reward, next_state, done


@dataclass
class EpisodeResult:
    episode: int
    total_reward: float
    total_training_reward: float
    steps: int
    success: bool
    final_status: str
    task_id: str
    done_reason: str
    action_history: List[str]
    root_cause_confirmed: bool
    mitigation_applied: bool
    service_restored: bool
    monitoring_added: bool
    stochastic_mode: str
    env_profile: str
    scenario_label: str


def compute_training_reward(
    prev_state: IncidentObservation,
    action: ActionCandidate,
    env_reward: float,
    next_state: IncidentObservation,
    done: bool,
) -> float:
    """
    Shape the learning reward toward successful incident resolution.

    This keeps the existing environment reward intact for the application while
    making the RL signal much more aligned with actually solving the incident.
    """

    shaped_reward = env_reward

    if not prev_state.root_cause_confirmed and next_state.root_cause_confirmed:
        shaped_reward += 1.10
    if not prev_state.mitigation_applied and next_state.mitigation_applied:
        shaped_reward += 0.85
    if not prev_state.service_restored and next_state.service_restored:
        shaped_reward += 1.45
    if not prev_state.monitoring_added and next_state.monitoring_added:
        shaped_reward += 0.35

    if action.action_type == ActionType.DO_NOTHING:
        shaped_reward -= 0.20
    if action.action_type == ActionType.RESTART_SERVICE:
        shaped_reward -= 0.20
    if next_state.last_action_error:
        shaped_reward -= 0.20
    if next_state.service_restored and not next_state.root_cause_confirmed:
        shaped_reward -= 0.25

    if done:
        if next_state.current_status == "resolved":
            shaped_reward += 2.20
            if next_state.root_cause_confirmed:
                shaped_reward += 0.80
        elif not next_state.service_restored:
            shaped_reward -= 1.30
        elif next_state.service_restored and next_state.current_status != "resolved":
            shaped_reward -= 1.25

    if next_state.service_restored and next_state.current_status != "resolved":
        shaped_reward -= 0.15

    return round(shaped_reward, 4)


def run_episode(env: ProductionIncidentEnv, policy: Policy) -> EpisodeResult:
    state = env.reset()
    valid_actions = extract_action_space(env)

    begin_episode = getattr(policy, "begin_episode", None)
    if callable(begin_episode):
        begin_episode(env.task, valid_actions)

    register_actions = getattr(policy, "register_actions", None)
    if callable(register_actions):
        register_actions(valid_actions)

    total_reward = 0.0
    total_training_reward = 0.0
    steps = 0
    done = False
    info: Dict[str, object] = {}

    while not done:
        action = policy.select_action(state, valid_actions)
        next_state, reward, done, info = env.step(action.to_incident_action())
        training_reward = compute_training_reward(state, action, reward, next_state, done)
        policy.observe(state, action, training_reward, next_state, done)
        total_reward += reward
        total_training_reward += training_reward
        steps += 1
        state = next_state

    success = state.current_status == "resolved"
    return EpisodeResult(
        episode=0,
        total_reward=round(total_reward, 4),
        total_training_reward=round(total_training_reward, 4),
        steps=steps,
        success=success,
        final_status=state.current_status,
        task_id=env.task.task_id,
        done_reason=str(info.get("done_reason", "unknown")),
        action_history=list(info.get("action_history", [])),
        root_cause_confirmed=state.root_cause_confirmed,
        mitigation_applied=state.mitigation_applied,
        service_restored=state.service_restored,
        monitoring_added=state.monitoring_added,
        stochastic_mode=str(info.get("stochastic_mode", "deterministic")),
        env_profile=str(info.get("dynamics_profile", "v1")),
        scenario_label=str(info.get("scenario_label", "default")),
    )


def save_rewards_to_csv(rewards: Sequence[float], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["episode", "reward"])
        for episode_number, reward in enumerate(rewards, start=1):
            writer.writerow([episode_number, reward])


def plot_rewards(rewards: Sequence[float], path: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 4))
    plt.plot(range(1, len(rewards) + 1), rewards, linewidth=2)
    plt.title("Episode Reward Curve")
    plt.xlabel("Episode")
    plt.ylabel("Total Reward")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return True


def train_loop(
    num_episodes: int,
    task_id: str = "easy",
    max_steps: Optional[int] = None,
    seed: int = 7,
    env_mode: str = "stochastic",
    env_profile: str = "v1",
    policy: Optional[Policy] = None,
    csv_path: Optional[Path] = None,
    plot_path: Optional[Path] = None,
) -> Tuple[List[float], List[EpisodeResult], Policy]:
    active_policy: Policy = policy or EpsilonGreedyPolicy(seed=seed)
    rewards: List[float] = []
    results: List[EpisodeResult] = []

    for episode_number in range(1, num_episodes + 1):
        env = ProductionIncidentEnv(
            task_id=task_id,
            max_steps=max_steps,
            stochastic_mode=env_mode,
            dynamics_profile=env_profile,
            random_seed=seed + episode_number,
        )
        result = run_episode(env, active_policy)
        result.episode = episode_number
        rewards.append(result.total_reward)
        results.append(result)
        print(
            f"Episode {episode_number:03d} | env_reward={result.total_reward:.4f} | "
            f"train_reward={result.total_training_reward:.4f} | steps={result.steps:02d} | "
            f"success={result.success} | root={result.root_cause_confirmed} | "
            f"restored={result.service_restored} | done={result.done_reason}"
        )
        decay = getattr(active_policy, "decay", None)
        if callable(decay):
            decay()

    if csv_path is not None:
        save_rewards_to_csv(rewards, csv_path)
    if plot_path is not None:
        created = plot_rewards(rewards, plot_path)
        if not created:
            print("Plot skipped: matplotlib is not installed.")

    return rewards, results, active_policy


def evaluate_random_policy(
    num_episodes: int,
    task_id: str,
    max_steps: Optional[int],
    seed: int,
    env_mode: str = "stochastic",
    env_profile: str = "v1",
) -> List[EpisodeResult]:
    policy = RandomPolicy(seed=seed)
    results: List[EpisodeResult] = []
    for episode_number in range(1, num_episodes + 1):
        env = ProductionIncidentEnv(
            task_id=task_id,
            max_steps=max_steps,
            stochastic_mode=env_mode,
            dynamics_profile=env_profile,
            random_seed=seed + (episode_number * 17),
        )
        result = run_episode(env, policy)
        result.episode = episode_number
        results.append(result)
        print(
            f"[random] Episode {episode_number:03d} | env_reward={result.total_reward:.4f} | "
            f"train_reward={result.total_training_reward:.4f} | steps={result.steps:02d} | "
            f"success={result.success} | root={result.root_cause_confirmed} | "
            f"restored={result.service_restored} | done={result.done_reason}"
        )
    return results


def summarize(results: Sequence[EpisodeResult], label: str) -> None:
    if not results:
        print(f"{label}: no results")
        return

    avg_reward = sum(result.total_reward for result in results) / len(results)
    avg_training_reward = sum(result.total_training_reward for result in results) / len(results)
    avg_steps = sum(result.steps for result in results) / len(results)
    reward_stddev = statistics.pstdev([result.total_reward for result in results]) if len(results) > 1 else 0.0
    success_rate = sum(1 for result in results if result.success) / len(results)
    root_cause_rate = sum(1 for result in results if result.root_cause_confirmed) / len(results)
    restore_rate = sum(1 for result in results if result.service_restored) / len(results)
    closure_gap_rate = sum(1 for result in results if result.service_restored and not result.success) / len(results)
    trajectory_diversity = len({tuple(result.action_history) for result in results}) / len(results)
    scenario_diversity = len({result.scenario_label for result in results}) / len(results)
    print(
        f"{label} summary | avg_env_reward={avg_reward:.4f} | "
        f"avg_train_reward={avg_training_reward:.4f} | avg_steps={avg_steps:.2f} | "
        f"success_rate={success_rate:.2%} | root_cause_rate={root_cause_rate:.2%} | "
        f"restore_rate={restore_rate:.2%} | closure_gap_rate={closure_gap_rate:.2%} | "
        f"reward_std={reward_stddev:.4f} | trajectory_diversity={trajectory_diversity:.2%} | "
        f"scenario_diversity={scenario_diversity:.2%}"
    )

    successful_runs = [result for result in results if result.success]
    if successful_runs:
        best_success = max(successful_runs, key=lambda result: result.total_training_reward)
        print(
            "Best successful trajectory | "
            f"steps={best_success.steps:02d} | actions={best_success.action_history}"
        )


def make_policy(policy_name: str, seed: int, hf_model: str) -> Policy:
    if policy_name == "random":
        return RandomPolicy(seed=seed)
    if policy_name == "hf":
        return HuggingFacePolicyAdapter(model_name=hf_model, seed=seed)
    return EpsilonGreedyPolicy(seed=seed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal RL training loop for ProductionIncidentEnv.")
    parser.add_argument("--task-id", default="easy", choices=["easy", "medium", "hard"], help="Incident task to train on.")
    parser.add_argument("--episodes", type=int, default=25, help="Number of epsilon-greedy training episodes.")
    parser.add_argument("--baseline-random", type=int, default=5, help="Number of random baseline episodes.")
    parser.add_argument("--policy", default="epsilon", choices=["epsilon", "random", "hf"], help="Policy used for the main run.")
    parser.add_argument("--hf-model", default="distilgpt2", help="HuggingFace model name for --policy hf.")
    parser.add_argument("--max-steps", type=int, default=None, help="Optional max steps override.")
    parser.add_argument(
        "--env-mode",
        default="stochastic",
        choices=["deterministic", "stochastic"],
        help="Environment dynamics mode. Use stochastic for harder, varied training.",
    )
    parser.add_argument(
        "--env-profile",
        default="v1",
        choices=["v1", "v2"],
        help="Environment profile. v1 preserves the current baseline, v2 enables stricter incident workflow dynamics.",
    )
    parser.add_argument("--seed", type=int, default=7, help="Random seed.")
    parser.add_argument("--csv", default="artifacts/rl_rewards.csv", help="Optional CSV output path.")
    parser.add_argument("--plot", default="artifacts/rl_rewards.png", help="Optional reward plot output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.baseline_random > 0:
        print(f"Running random baseline on task '{args.task_id}' ({args.env_mode}, profile={args.env_profile})...")
        random_results = evaluate_random_policy(
            num_episodes=args.baseline_random,
            task_id=args.task_id,
            max_steps=args.max_steps,
            seed=args.seed,
            env_mode=args.env_mode,
            env_profile=args.env_profile,
        )
        summarize(random_results, "Random baseline")
        print()

    policy = make_policy(args.policy, args.seed, args.hf_model)
    label = "HuggingFace policy" if args.policy == "hf" else "Random policy" if args.policy == "random" else "Epsilon-greedy training"
    print(f"Running {args.policy} policy on task '{args.task_id}' ({args.env_mode}, profile={args.env_profile})...")
    rewards, train_results, _policy = train_loop(
        num_episodes=args.episodes,
        task_id=args.task_id,
        max_steps=args.max_steps,
        seed=args.seed,
        env_mode=args.env_mode,
        env_profile=args.env_profile,
        policy=policy,
        csv_path=Path(args.csv) if args.csv else None,
        plot_path=Path(args.plot) if args.plot else None,
    )
    summarize(train_results, label)
    print(f"Recorded {len(rewards)} rewards.")


if __name__ == "__main__":
    main()
