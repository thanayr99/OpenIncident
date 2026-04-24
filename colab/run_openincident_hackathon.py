from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rl_training import evaluate_random_policy, make_policy, summarize, train_loop


def build_summary(results: Sequence[Any], label: str) -> Dict[str, Any]:
    if not results:
        return {
            "label": label,
            "episodes": 0,
            "avg_env_reward": 0.0,
            "avg_train_reward": 0.0,
            "avg_steps": 0.0,
            "success_rate": 0.0,
            "root_cause_rate": 0.0,
            "restore_rate": 0.0,
            "closure_gap_rate": 0.0,
            "best_successful_trajectory": None,
        }

    avg_env_reward = sum(result.total_reward for result in results) / len(results)
    avg_train_reward = sum(result.total_training_reward for result in results) / len(results)
    avg_steps = sum(result.steps for result in results) / len(results)
    success_rate = sum(1 for result in results if result.success) / len(results)
    root_cause_rate = sum(1 for result in results if result.root_cause_confirmed) / len(results)
    restore_rate = sum(1 for result in results if result.service_restored) / len(results)
    closure_gap_rate = sum(1 for result in results if result.service_restored and not result.success) / len(results)

    successful_runs = [result for result in results if result.success]
    best_success = None
    if successful_runs:
        winner = max(successful_runs, key=lambda result: result.total_training_reward)
        best_success = {
            "episode": winner.episode,
            "steps": winner.steps,
            "actions": list(winner.action_history),
            "env_reward": winner.total_reward,
            "train_reward": winner.total_training_reward,
        }

    return {
        "label": label,
        "episodes": len(results),
        "avg_env_reward": round(avg_env_reward, 4),
        "avg_train_reward": round(avg_train_reward, 4),
        "avg_steps": round(avg_steps, 2),
        "success_rate": round(success_rate, 4),
        "root_cause_rate": round(root_cause_rate, 4),
        "restore_rate": round(restore_rate, 4),
        "closure_gap_rate": round(closure_gap_rate, 4),
        "best_successful_trajectory": best_success,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Colab-friendly hackathon runner for OpenIncident X.")
    parser.add_argument("--task-id", default="medium", choices=["easy", "medium", "hard"])
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--baseline-random", type=int, default=5)
    parser.add_argument("--policy", default="epsilon", choices=["epsilon", "random", "hf"])
    parser.add_argument("--hf-model", default="distilgpt2")
    parser.add_argument("--env-mode", default="stochastic", choices=["deterministic", "stochastic"])
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--output-dir", default="artifacts/colab_demo")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_results = []
    if args.baseline_random > 0:
        print(f"Running baseline on task '{args.task_id}' ({args.env_mode})...")
        baseline_results = evaluate_random_policy(
            num_episodes=args.baseline_random,
            task_id=args.task_id,
            max_steps=args.max_steps,
            seed=args.seed,
            env_mode=args.env_mode,
        )
        summarize(baseline_results, "Random baseline")
        print()

    csv_path = output_dir / f"{args.task_id}_{args.policy}_rewards.csv"
    plot_path = output_dir / f"{args.task_id}_{args.policy}_rewards.png"
    metrics_path = output_dir / f"{args.task_id}_{args.policy}_metrics.json"

    print(f"Running {args.policy} policy on task '{args.task_id}' ({args.env_mode})...")
    policy = make_policy(args.policy, args.seed, args.hf_model)
    rewards, trained_results, _policy = train_loop(
        num_episodes=args.episodes,
        task_id=args.task_id,
        max_steps=args.max_steps,
        seed=args.seed,
        env_mode=args.env_mode,
        policy=policy,
        csv_path=csv_path,
        plot_path=plot_path,
    )
    label = "HuggingFace policy" if args.policy == "hf" else "Random policy" if args.policy == "random" else "Epsilon-greedy training"
    summarize(trained_results, label)
    print(f"Recorded {len(rewards)} rewards.")

    payload = {
        "task_id": args.task_id,
        "policy": args.policy,
        "env_mode": args.env_mode,
        "seed": args.seed,
        "baseline": build_summary(baseline_results, "Random baseline"),
        "trained": build_summary(trained_results, label),
        "artifacts": {
            "csv": str(csv_path),
            "plot": str(plot_path),
            "metrics": str(metrics_path),
        },
    }

    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print()
    print(f"Saved metrics summary to {metrics_path}")


if __name__ == "__main__":
    main()
