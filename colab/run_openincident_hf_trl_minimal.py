from __future__ import annotations

import argparse
import inspect
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rl_training import (  # noqa: E402
    ActionCandidate,
    EpsilonGreedyPolicy,
    compute_training_reward,
    extract_action_space,
    render_state_summary,
)
from server.environment import ProductionIncidentEnv  # noqa: E402


def action_to_response(action: ActionCandidate) -> str:
    payload: Dict[str, str] = {"action_type": action.action_type.value}
    if action.target:
        payload["target"] = action.target
    if action.content:
        payload["content"] = action.content
    return json.dumps(payload, ensure_ascii=True)


def build_prompt(state_summary: str, valid_actions: Sequence[ActionCandidate]) -> str:
    action_types = sorted({action.action_type.value for action in valid_actions})
    return (
        "You are the Reliability Agent for incident response.\n"
        "Choose the next best action based on the current state.\n"
        f"Allowed action types: {', '.join(action_types)}\n\n"
        "Current incident state:\n"
        f"{state_summary}\n\n"
        "Return one JSON object with keys: action_type, target (optional), content (optional)."
    )


def collect_sft_dataset(
    *,
    task_id: str,
    env_mode: str,
    env_profile: str,
    episodes: int,
    warmup_episodes: int,
    keep_failed_ratio: float,
    seed: int,
    output_path: Path,
) -> Dict[str, Any]:
    policy = EpsilonGreedyPolicy(
        seed=seed,
        epsilon=0.35,
        min_epsilon=0.05,
        epsilon_decay=0.975,
        guided_flow=True,
    )
    collector_rng = random.Random(seed + 1103)

    records: List[Dict[str, Any]] = []
    successful_episodes = 0
    failed_episodes_kept = 0

    total_episodes = warmup_episodes + episodes
    for episode_number in range(1, total_episodes + 1):
        env = ProductionIncidentEnv(
            task_id=task_id,
            stochastic_mode=env_mode,
            dynamics_profile=env_profile,
            random_seed=seed + (episode_number * 19),
        )
        state = env.reset()
        valid_actions = extract_action_space(env)
        policy.begin_episode(env.task, valid_actions)

        done = False
        info: Dict[str, Any] = {}
        step_number = 0
        episode_records: List[Dict[str, Any]] = []

        while not done:
            action = policy.select_action(state, valid_actions)
            state_summary = render_state_summary(state)
            prompt = build_prompt(state_summary, valid_actions)
            next_state, env_reward, done, info = env.step(action.to_incident_action())
            train_reward = compute_training_reward(state, action, env_reward, next_state, done)
            policy.observe(state, action, train_reward, next_state, done)
            step_number += 1

            if episode_number > warmup_episodes and action.action_type.value != "do_nothing":
                response = action_to_response(action)
                episode_records.append(
                    {
                        "text": f"### User:\n{prompt}\n\n### Assistant:\n{response}",
                        "prompt": prompt,
                        "response": response,
                        "completion": response,
                        "episode": episode_number - warmup_episodes,
                        "step": step_number,
                        "env_reward": round(env_reward, 4),
                        "train_reward": round(train_reward, 4),
                        "done": done,
                        "scenario_label": str(info.get("scenario_label", "default")),
                    }
                )
            state = next_state

        if episode_number <= warmup_episodes:
            policy.decay()
            continue

        episode_success = state.current_status == "resolved"
        if episode_success:
            successful_episodes += 1
            records.extend(episode_records)
        elif collector_rng.random() < keep_failed_ratio:
            failed_episodes_kept += 1
            records.extend(episode_records)

        policy.decay()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    return {
        "dataset_path": str(output_path),
        "records": len(records),
        "episodes_collected": episodes,
        "warmup_episodes": warmup_episodes,
        "successful_episodes": successful_episodes,
        "failed_episodes_kept": failed_episodes_kept,
        "keep_failed_ratio": keep_failed_ratio,
        "task_id": task_id,
        "env_mode": env_mode,
        "env_profile": env_profile,
    }


def _build_trainer(
    *,
    trainer_cls: Any,
    model: Any,
    args: Any,
    dataset: Any,
    tokenizer: Any,
    max_seq_length: int,
) -> Any:
    trainer_sig = inspect.signature(trainer_cls.__init__)
    base_kwargs: Dict[str, Any] = {}
    if "processing_class" in trainer_sig.parameters:
        base_kwargs["processing_class"] = tokenizer
    elif "tokenizer" in trainer_sig.parameters:
        base_kwargs["tokenizer"] = tokenizer

    try:
        return trainer_cls(model=model, args=args, train_dataset=dataset, **base_kwargs)
    except TypeError:
        if "formatting_func" in trainer_sig.parameters:
            fallback_kwargs = dict(base_kwargs)
            fallback_kwargs["formatting_func"] = lambda example: example["text"]
            return trainer_cls(model=model, args=args, train_dataset=dataset, **fallback_kwargs)
        raise


def run_trl_training(
    *,
    dataset_path: Path,
    model_id: str,
    output_dir: Path,
    learning_rate: float,
    num_train_epochs: float,
    batch_size: int,
    gradient_accumulation_steps: int,
    max_seq_length: int,
    seed: int,
) -> Dict[str, Any]:
    try:
        import torch
        cuda_available = bool(torch.cuda.is_available())
    except Exception:
        cuda_available = False

    try:
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
        from trl import SFTTrainer

        try:
            from trl import SFTConfig  # type: ignore
        except ImportError:
            SFTConfig = None
    except ImportError as exc:
        raise RuntimeError(
            "Missing HuggingFace dependencies. Install: "
            "pip install trl transformers datasets accelerate peft"
        ) from exc

    dataset = load_dataset("json", data_files=str(dataset_path), split="train")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_id)

    args_common = {
        "output_dir": str(output_dir / "checkpoints"),
        "per_device_train_batch_size": batch_size,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "learning_rate": learning_rate,
        "num_train_epochs": num_train_epochs,
        "logging_steps": 5,
        "save_strategy": "no",
        "report_to": "none",
        "seed": seed,
    }
    if not cuda_available:
        args_common["use_cpu"] = True
        args_common["bf16"] = False
        args_common["fp16"] = False

    if SFTConfig is not None:
        sft_sig = inspect.signature(SFTConfig.__init__)
        sft_kwargs = dict(args_common)
        if "max_seq_length" in sft_sig.parameters:
            sft_kwargs["max_seq_length"] = max_seq_length
        elif "max_length" in sft_sig.parameters:
            sft_kwargs["max_length"] = max_seq_length
        if "dataset_text_field" in sft_sig.parameters:
            sft_kwargs["dataset_text_field"] = "text"
        training_args = SFTConfig(**sft_kwargs)
    else:
        training_args = TrainingArguments(**args_common)

    trainer = _build_trainer(
        trainer_cls=SFTTrainer,
        model=model,
        args=training_args,
        dataset=dataset,
        tokenizer=tokenizer,
        max_seq_length=max_seq_length,
    )
    train_result = trainer.train()

    model_output_dir = output_dir / "trained_model"
    model_output_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(model_output_dir))
    tokenizer.save_pretrained(str(model_output_dir))

    metrics = dict(train_result.metrics)
    metrics["train_samples"] = len(dataset)
    metrics["model_id"] = model_id
    metrics["dataset_path"] = str(dataset_path)
    metrics["model_output_dir"] = str(model_output_dir)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal HuggingFace TRL SFT training for OpenIncident X environment trajectories."
    )
    parser.add_argument("--task-id", default="medium", choices=["easy", "medium", "hard"])
    parser.add_argument("--env-mode", default="stochastic", choices=["deterministic", "stochastic"])
    parser.add_argument("--env-profile", default="v1", choices=["v1", "v2"])
    parser.add_argument("--episodes", type=int, default=80, help="Episodes to collect after warmup.")
    parser.add_argument("--warmup-episodes", type=int, default=20, help="Episodes used to warm up the teacher policy.")
    parser.add_argument("--keep-failed-ratio", type=float, default=0.15, help="Fraction of failed episodes retained for diversity.")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--model-id", default="sshleifer/tiny-gpt2")
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--num-train-epochs", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=2)
    parser.add_argument("--max-seq-length", type=int, default=512)
    parser.add_argument("--output-dir", default="artifacts/trl_minimal")
    parser.add_argument("--skip-train", action="store_true", help="Only generate dataset JSONL, skip HF TRL training.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_suffix = "" if args.env_profile == "v1" else f"_{args.env_profile}"
    dataset_path = output_dir / f"{args.task_id}_{args.env_mode}{profile_suffix}_sft_dataset.jsonl"
    dataset_summary_path = output_dir / f"{args.task_id}_{args.env_mode}{profile_suffix}_dataset_summary.json"
    train_summary_path = output_dir / f"{args.task_id}_{args.env_mode}{profile_suffix}_trl_summary.json"

    print(
        f"Collecting environment trajectories for SFT dataset "
        f"(mode={args.env_mode}, profile={args.env_profile})..."
    )
    dataset_summary = collect_sft_dataset(
        task_id=args.task_id,
        env_mode=args.env_mode,
        env_profile=args.env_profile,
        episodes=args.episodes,
        warmup_episodes=args.warmup_episodes,
        keep_failed_ratio=args.keep_failed_ratio,
        seed=args.seed,
        output_path=dataset_path,
    )
    dataset_summary_path.write_text(json.dumps(dataset_summary, indent=2), encoding="utf-8")
    print(f"Dataset saved: {dataset_path}")
    print(f"Records: {dataset_summary['records']}")
    print(f"Successful episodes retained: {dataset_summary['successful_episodes']}/{args.episodes}")

    if args.skip_train:
        print("Skipping HF TRL training (--skip-train enabled).")
        return

    print(f"Running HF TRL SFT training with model '{args.model_id}'...")
    train_summary = run_trl_training(
        dataset_path=dataset_path,
        model_id=args.model_id,
        output_dir=output_dir,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        max_seq_length=args.max_seq_length,
        seed=args.seed,
    )
    train_summary_path.write_text(json.dumps(train_summary, indent=2), encoding="utf-8")
    print(f"TRL summary saved: {train_summary_path}")
    if "train_loss" in train_summary:
        print(f"Final train_loss: {train_summary['train_loss']}")


if __name__ == "__main__":
    main()
