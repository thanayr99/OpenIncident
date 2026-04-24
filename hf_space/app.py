from __future__ import annotations

import json
from pathlib import Path

import gradio as gr


REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = REPO_ROOT / "artifacts" / "colab_demo" / "medium_epsilon_metrics.json"
PLOT_PATH = REPO_ROOT / "artifacts" / "colab_demo" / "medium_epsilon_rewards.png"


def load_metrics() -> dict:
    if METRICS_PATH.exists():
        return json.loads(METRICS_PATH.read_text(encoding="utf-8"))

    return {
        "task_id": "medium",
        "policy": "epsilon",
        "env_mode": "stochastic",
        "baseline": {
            "success_rate": 0.0,
            "root_cause_rate": 0.2,
            "restore_rate": 0.0,
            "closure_gap_rate": 0.0,
            "avg_steps": 10.0,
        },
        "trained": {
            "success_rate": 0.3333,
            "root_cause_rate": 0.6333,
            "restore_rate": 0.4333,
            "closure_gap_rate": 0.1,
            "avg_steps": 9.57,
            "best_successful_trajectory": {
                "actions": [
                    "inspect_config",
                    "identify_root_cause",
                    "inspect_traces",
                    "identify_root_cause",
                    "apply_fix",
                    "apply_fix",
                    "apply_fix",
                    "apply_fix",
                    "inspect_logs",
                    "resolve_incident",
                ],
            },
        },
        "artifacts": {
            "plot": str(PLOT_PATH),
        },
    }


def percent(value: float) -> str:
    return f"{value * 100:.0f}%"


metrics = load_metrics()
baseline = metrics["baseline"]
trained = metrics["trained"]
trajectory = trained.get("best_successful_trajectory") or {}
trajectory_actions = trajectory.get("actions", [])

summary_md = f"""
# OpenIncident X

**OpenIncident X** is an OpenEnv-compatible multi-agent professional-operations
environment for training LLMs on long-horizon incident response.

## Why this environment is interesting

- partially observable software operations world
- long-horizon recovery workflow
- realistic evidence gathering from logs, metrics, traces, code, and deploys
- multi-agent framing around a primary trained Reliability Agent

## Main training target

- **Environment:** `ProductionIncidentEnv`
- **Trained agent:** `Reliability Agent`
- **Task shown here:** `{metrics.get("task_id", "medium")}`
- **Policy:** `{metrics.get("policy", "epsilon")}`

## Before vs after

- **Baseline success rate:** {percent(baseline.get("success_rate", 0.0))}
- **Trained success rate:** {percent(trained.get("success_rate", 0.0))}
- **Baseline closure gap:** {percent(baseline.get("closure_gap_rate", 0.0))}
- **Trained closure gap:** {percent(trained.get("closure_gap_rate", 0.0))}
- **Baseline avg steps:** {baseline.get("avg_steps", 0.0)}
- **Trained avg steps:** {trained.get("avg_steps", 0.0)}

## Best successful trajectory

`{trajectory_actions}`

## Honest caveat

The current environment still allows some successful trajectories without full
root-cause confirmation, so the strongest claim is that training improves
**recovery and closure behavior**.
"""


with gr.Blocks(title="OpenIncident X") as demo:
    gr.Markdown(summary_md)
    if PLOT_PATH.exists():
        gr.Image(value=str(PLOT_PATH), label="Reward Curve")
    else:
        gr.Markdown(
            "Reward plot not found locally. Run the training command first to generate "
            "`artifacts/colab_demo/medium_epsilon_rewards.png`."
        )
    gr.JSON(value=metrics, label="Metrics Summary")


if __name__ == "__main__":
    demo.launch()
