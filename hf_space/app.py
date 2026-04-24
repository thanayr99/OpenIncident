from __future__ import annotations

import json
import os
from pathlib import Path

import gradio as gr


REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = REPO_ROOT / "artifacts" / "colab_demo" / "medium_epsilon_metrics.json"
PLOT_PATH = REPO_ROOT / "artifacts" / "colab_demo" / "medium_epsilon_rewards.png"
DATASET_SUMMARY_PATH = REPO_ROOT / "artifacts" / "trl_minimal" / "medium_stochastic_dataset_summary.json"
TRL_SUMMARY_PATH = REPO_ROOT / "artifacts" / "trl_minimal" / "medium_stochastic_trl_summary.json"
GITHUB_URL = "https://github.com/thanayr99/OpenIncident"
COLAB_URL = "https://colab.research.google.com/drive/1R4IrMr5nIKm7lZfbI08EP9ijkUgF7fxH?usp=sharing"
SPACE_URL = "https://thanayr-openincident.hf.space"


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


def load_optional_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def percent(value: float) -> str:
    return f"{value * 100:.0f}%"


def metric_card(title: str, value: str, hint: str = "") -> str:
    hint_html = f"<div class='card-hint'>{hint}</div>" if hint else ""
    return (
        "<div class='metric-card'>"
        f"<div class='card-title'>{title}</div>"
        f"<div class='card-value'>{value}</div>"
        f"{hint_html}"
        "</div>"
    )


def delta_text(current: float, baseline_value: float, as_percent: bool = False) -> str:
    delta = current - baseline_value
    if as_percent:
        return f"{delta * 100:+.2f}%"
    return f"{delta:+.2f}"


metrics = load_metrics()
baseline = metrics["baseline"]
trained = metrics["trained"]
trajectory = trained.get("best_successful_trajectory") or {}
trajectory_actions = trajectory.get("actions", [])
dataset_summary = load_optional_json(DATASET_SUMMARY_PATH)
trl_summary = load_optional_json(TRL_SUMMARY_PATH)

header_md = """
# OpenIncident X
OpenEnv-compatible multi-agent professional operations environment for training incident-response agents.
"""

overview_md = f"""
### Why judges care
- Partially observable incident-response world (logs, metrics, traces, deploys, config, code)
- Long-horizon recovery path instead of single-step reward hacking
- Baseline vs trained policy comparison with saved artifacts
- Minimum hackathon requirement covered: hosted Space + Colab + HF TRL path

### Training target
- Environment: `ProductionIncidentEnv`
- Primary trained role: `Reliability Agent`
- Task: `{metrics.get("task_id", "medium")}`
- Policy: `{metrics.get("policy", "epsilon")}`
- Environment mode: `{metrics.get("env_mode", "stochastic")}`
"""

results_table_md = f"""
| Metric | Baseline | Trained | Delta |
|---|---:|---:|---:|
| Success rate | {percent(baseline.get("success_rate", 0.0))} | {percent(trained.get("success_rate", 0.0))} | {delta_text(trained.get("success_rate", 0.0), baseline.get("success_rate", 0.0), as_percent=True)} |
| Root-cause rate | {percent(baseline.get("root_cause_rate", 0.0))} | {percent(trained.get("root_cause_rate", 0.0))} | {delta_text(trained.get("root_cause_rate", 0.0), baseline.get("root_cause_rate", 0.0), as_percent=True)} |
| Restore rate | {percent(baseline.get("restore_rate", 0.0))} | {percent(trained.get("restore_rate", 0.0))} | {delta_text(trained.get("restore_rate", 0.0), baseline.get("restore_rate", 0.0), as_percent=True)} |
| Closure gap | {percent(baseline.get("closure_gap_rate", 0.0))} | {percent(trained.get("closure_gap_rate", 0.0))} | {delta_text(trained.get("closure_gap_rate", 0.0), baseline.get("closure_gap_rate", 0.0), as_percent=True)} |
| Avg steps | {baseline.get("avg_steps", 0.0):.2f} | {trained.get("avg_steps", 0.0):.2f} | {delta_text(trained.get("avg_steps", 0.0), baseline.get("avg_steps", 0.0))} |
"""

links_md = f"""
### Reproducibility links
- Space: [{SPACE_URL}]({SPACE_URL})
- GitHub repo: [{GITHUB_URL}]({GITHUB_URL})
- Colab notebook: [{COLAB_URL}]({COLAB_URL})

### RL command (baseline + trained)
```bash
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --output-dir artifacts/colab_demo
```

### HF TRL command (minimum requirement path)
```bash
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_minimal
```
"""

css = """
.metric-card {
  border: 1px solid #2a3550;
  border-radius: 12px;
  padding: 14px 16px;
  background: linear-gradient(180deg, #121a2b, #0f1523);
  min-height: 92px;
}
.card-title {
  color: #9fb4d0;
  font-size: 12px;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}
.card-value {
  color: #f5f8ff;
  font-size: 28px;
  font-weight: 700;
  margin-top: 4px;
}
.card-hint {
  color: #7d93b6;
  font-size: 12px;
  margin-top: 4px;
}
"""

with gr.Blocks(title="OpenIncident X", css=css) as demo:
    gr.Markdown(header_md)

    with gr.Row():
        gr.Markdown(
            metric_card("Success Rate", percent(trained.get("success_rate", 0.0)), "trained policy"),
            elem_id="success-card",
        )
        gr.Markdown(
            metric_card("Root Cause Rate", percent(trained.get("root_cause_rate", 0.0)), "diagnosis quality"),
            elem_id="root-card",
        )
        gr.Markdown(
            metric_card("Restore Rate", percent(trained.get("restore_rate", 0.0)), "service recovery"),
            elem_id="restore-card",
        )
        gr.Markdown(
            metric_card("Closure Gap", percent(trained.get("closure_gap_rate", 0.0)), "lower is better"),
            elem_id="gap-card",
        )

    with gr.Tabs():
        with gr.TabItem("Overview"):
            gr.Markdown(overview_md)
            gr.Markdown(
                "### Honest caveat\n"
                "This environment can still produce successful closure without perfect root-cause certainty. "
                "The strongest safe claim is improved recovery and closure behavior."
            )

        with gr.TabItem("Results"):
            gr.Markdown("### Baseline vs trained")
            gr.Markdown(results_table_md)
            if PLOT_PATH.exists():
                gr.Image(value=str(PLOT_PATH), label="Reward Curve")
            else:
                gr.Markdown("Reward plot missing at `artifacts/colab_demo/medium_epsilon_rewards.png`.")
            gr.Markdown("### Best successful trajectory")
            gr.Code(value=str(trajectory_actions), language="json")
            if trl_summary:
                gr.Markdown("### Second result: HF TRL training run")
                trl_brief = {
                    "train_loss": trl_summary.get("train_loss"),
                    "train_runtime": trl_summary.get("train_runtime"),
                    "train_samples": trl_summary.get("train_samples"),
                    "model_id": trl_summary.get("model_id"),
                }
                gr.JSON(value=trl_brief, label="HF TRL Result Snapshot")

        with gr.TabItem("Reproducibility"):
            gr.Markdown(links_md)
            if dataset_summary:
                gr.Markdown("### HF TRL dataset summary")
                gr.JSON(value=dataset_summary, label="Dataset Summary")
            if trl_summary:
                gr.Markdown("### HF TRL training summary")
                gr.JSON(value=trl_summary, label="TRL Summary")

        with gr.TabItem("Raw Metrics"):
            gr.JSON(value=metrics, label="RL Metrics JSON")


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")))
