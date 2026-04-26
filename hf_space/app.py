from __future__ import annotations

import json
import os
from pathlib import Path

import gradio as gr


REPO_ROOT = Path(__file__).resolve().parent.parent

PRIMARY_METRICS_PATH = (
    REPO_ROOT / "artifacts" / "colab_demo_v1" / "medium_epsilon_metrics.json"
)
LEGACY_METRICS_PATH = REPO_ROOT / "artifacts" / "colab_demo" / "medium_epsilon_metrics.json"
V2_METRICS_PATH = (
    REPO_ROOT / "artifacts" / "colab_demo_v2_tuned4_full" / "medium_epsilon_v2_metrics.json"
)

PRIMARY_PLOT_PATH = REPO_ROOT / "artifacts" / "colab_demo_v1" / "medium_epsilon_rewards.png"
LEGACY_PLOT_PATH = REPO_ROOT / "artifacts" / "colab_demo" / "medium_epsilon_rewards.png"
V2_PLOT_PATH = (
    REPO_ROOT / "artifacts" / "colab_demo_v2_tuned4_full" / "medium_epsilon_v2_rewards.png"
)
TRL_LOSS_PLOT_PATH = (
    REPO_ROOT / "artifacts" / "trl_loss_proof" / "medium_stochastic_v2_trl_loss.png"
)

DATASET_SUMMARY_PATH = (
    REPO_ROOT / "artifacts" / "trl_loss_proof" / "medium_stochastic_v2_dataset_summary.json"
)
TRL_SUMMARY_PATH = (
    REPO_ROOT / "artifacts" / "trl_loss_proof" / "medium_stochastic_v2_trl_summary.json"
)

GITHUB_URL = "https://github.com/thanayr99/OpenIncident"
COLAB_URL = "https://colab.research.google.com/drive/1R4IrMr5nIKm7lZfbI08EP9ijkUgF7fxH?usp=sharing"
SPACE_HUB_URL = "https://huggingface.co/spaces/thanayr/OpenIncident"
SPACE_APP_URL = "https://thanayr-openincident.hf.space"
APP_URL = "https://open-incident.vercel.app/"
YOUTUBE_URL = "https://youtu.be/8L-1TsajsTA?si=2ZaoWftUeKxj0jqS"
BLOG_URL = "https://huggingface.co/spaces/thanayr/OpenIncident/blob/main/Blog.MD"
SCRIPT_URL = "https://huggingface.co/spaces/thanayr/OpenIncident/blob/main/VIDEO_SCRIPT_FINAL.md"


def load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_v1_metrics() -> dict:
    source = PRIMARY_METRICS_PATH if PRIMARY_METRICS_PATH.exists() else LEGACY_METRICS_PATH
    raw = load_json(source)
    if raw:
        return raw
    return {
        "task_id": "medium",
        "policy": "epsilon",
        "env_mode": "stochastic",
        "baseline": {
            "success_rate": 0.0,
            "root_cause_rate": 0.2,
            "restore_rate": 0.0,
            "closure_gap_rate": 0.0,
            "avg_env_reward": 0.6276,
            "avg_steps": 10.0,
        },
        "trained": {
            "success_rate": 0.2667,
            "root_cause_rate": 0.6333,
            "restore_rate": 0.3,
            "closure_gap_rate": 0.0333,
            "avg_env_reward": 1.0838,
            "avg_steps": 9.6,
            "best_successful_trajectory": {
                "steps": 10,
                "actions": [
                    "identify_root_cause",
                    "inspect_traces",
                    "identify_root_cause",
                    "inspect_logs",
                    "identify_root_cause",
                    "apply_fix",
                    "apply_fix",
                    "apply_fix",
                    "inspect_deploys",
                    "resolve_incident",
                ],
            },
        },
    }


def as_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def as_pct_compact(value: float) -> str:
    return f"{value * 100:.0f}%"


def delta_pct(current: float, baseline: float) -> str:
    return f"{(current - baseline) * 100:+.1f}%"


def kpi_card(title: str, value: str, subtitle: str, tone: str = "blue") -> str:
    return (
        f"<div class='kpi {tone}'>"
        f"<div class='kpi-title'>{title}</div>"
        f"<div class='kpi-value'>{value}</div>"
        f"<div class='kpi-sub'>{subtitle}</div>"
        "</div>"
    )


v1 = load_v1_metrics()
v2 = load_json(V2_METRICS_PATH)
dataset_summary = load_json(DATASET_SUMMARY_PATH)
trl_summary = load_json(TRL_SUMMARY_PATH)

baseline = v1.get("baseline", {})
trained = v1.get("trained", {})
trajectory = trained.get("best_successful_trajectory", {})
actions = trajectory.get("actions", [])

v2_baseline = v2.get("baseline", {})
v2_trained = v2.get("trained", {})

plot_v1 = PRIMARY_PLOT_PATH if PRIMARY_PLOT_PATH.exists() else LEGACY_PLOT_PATH
plot_v2 = V2_PLOT_PATH
plot_trl = TRL_LOSS_PLOT_PATH

hero_html = f"""
<section class="hero">
  <div class="hero-badge">OpenEnv India Hackathon 2026 Final Submission</div>
  <h1>OpenIncident X</h1>
  <p class="hero-sub">
    Multi-agent incident response platform + trainable RL environment for long-horizon,
    partially observable production outages.
  </p>
  <p class="hero-story">
    It is 2 AM. Alerts are firing. Logs and metrics disagree. OpenIncident X trains agents to
    inspect, diagnose, recover, and close incidents safely, not just explain them.
  </p>
  <div class="hero-links">
    <a href="{SPACE_APP_URL}" target="_blank">HF Space App</a>
    <a href="{APP_URL}" target="_blank">Live Product (Vercel)</a>
    <a href="{YOUTUBE_URL}" target="_blank">YouTube Demo</a>
    <a href="{COLAB_URL}" target="_blank">Colab Notebook</a>
    <a href="{GITHUB_URL}" target="_blank">GitHub Repo</a>
  </div>
</section>
"""

story_md = """
## Story Narrative (Judge-Facing)

### 1) The problem
Production incidents are noisy, ambiguous, and expensive. A single wrong action can increase downtime.

### 2) Why this project
Most AI systems can explain incidents, but they do not reliably handle them end-to-end:
inspect -> diagnose -> fix -> verify -> close.

### 3) What OpenIncident X adds
- Multi-agent product workflow for operational reasoning.
- OpenEnv-compatible `ProductionIncidentEnv` for measurable training.
- Evidence-backed RL comparison with saved artifacts and reproducible commands.

### 4) Why judges should care
This is not a toy game. It is a realistic software-operations world with partial observability,
long-horizon action dependencies, and safety-sensitive decision paths.
"""

requirements_md = f"""
## Submission Coverage (Non-Negotiables)

- OpenEnv latest pinned: `openenv-core==0.2.3`
- Environment hosted on HF Space: [{SPACE_HUB_URL}]({SPACE_HUB_URL})
- Working training scripts:
  - RL runner: `colab/run_openincident_hackathon.py`
  - HF TRL runner: `colab/run_openincident_hf_trl_minimal.py`
- Colab rerun notebook: [{COLAB_URL}]({COLAB_URL})
- Real training evidence committed:
  - reward plots (`v1`, `v2`)
  - TRL loss plot + CSV
- Mini-blog MD: [{BLOG_URL}]({BLOG_URL})
- YouTube demo: [{YOUTUBE_URL}]({YOUTUBE_URL})
- Full video script: [{SCRIPT_URL}]({SCRIPT_URL})
- Live product app: [{APP_URL}]({APP_URL})
"""

results_md = f"""
## Results Snapshot

### Official packet (v1: stochastic medium)

| Metric | Baseline | Trained | Delta |
|---|---:|---:|---:|
| Success rate | {as_pct(baseline.get("success_rate", 0.0))} | {as_pct(trained.get("success_rate", 0.0))} | {delta_pct(trained.get("success_rate", 0.0), baseline.get("success_rate", 0.0))} |
| Root-cause rate | {as_pct(baseline.get("root_cause_rate", 0.0))} | {as_pct(trained.get("root_cause_rate", 0.0))} | {delta_pct(trained.get("root_cause_rate", 0.0), baseline.get("root_cause_rate", 0.0))} |
| Restore rate | {as_pct(baseline.get("restore_rate", 0.0))} | {as_pct(trained.get("restore_rate", 0.0))} | {delta_pct(trained.get("restore_rate", 0.0), baseline.get("restore_rate", 0.0))} |
| Closure gap | {as_pct(baseline.get("closure_gap_rate", 0.0))} | {as_pct(trained.get("closure_gap_rate", 0.0))} | {delta_pct(trained.get("closure_gap_rate", 0.0), baseline.get("closure_gap_rate", 0.0))} |
| Avg env reward | {baseline.get("avg_env_reward", 0.0):.4f} | {trained.get("avg_env_reward", 0.0):.4f} | {trained.get("avg_env_reward", 0.0) - baseline.get("avg_env_reward", 0.0):+.4f} |
| Avg steps | {baseline.get("avg_steps", 0.0):.2f} | {trained.get("avg_steps", 0.0):.2f} | {trained.get("avg_steps", 0.0) - baseline.get("avg_steps", 0.0):+.2f} |

### Harder profile (v2: robustness)

| Metric | Baseline | Trained | Delta |
|---|---:|---:|---:|
| Success rate | {as_pct(v2_baseline.get("success_rate", 0.0))} | {as_pct(v2_trained.get("success_rate", 0.0))} | {delta_pct(v2_trained.get("success_rate", 0.0), v2_baseline.get("success_rate", 0.0))} |
| Root-cause rate | {as_pct(v2_baseline.get("root_cause_rate", 0.0))} | {as_pct(v2_trained.get("root_cause_rate", 0.0))} | {delta_pct(v2_trained.get("root_cause_rate", 0.0), v2_baseline.get("root_cause_rate", 0.0))} |
| Restore rate | {as_pct(v2_baseline.get("restore_rate", 0.0))} | {as_pct(v2_trained.get("restore_rate", 0.0))} | {delta_pct(v2_trained.get("restore_rate", 0.0), v2_baseline.get("restore_rate", 0.0))} |
| Closure gap | {as_pct(v2_baseline.get("closure_gap_rate", 0.0))} | {as_pct(v2_trained.get("closure_gap_rate", 0.0))} | {delta_pct(v2_trained.get("closure_gap_rate", 0.0), v2_baseline.get("closure_gap_rate", 0.0))} |
"""

repro_md = """
## Reproducibility

### RL run (official v1 packet)
```bash
python colab/run_openincident_hackathon.py --task-id medium --episodes 30 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v1 --output-dir artifacts/colab_demo_v1
```

### RL run (harder v2 packet)
```bash
python colab/run_openincident_hackathon.py --task-id medium --episodes 80 --baseline-random 5 --policy epsilon --env-mode stochastic --env-profile v2 --output-dir artifacts/colab_demo_v2_tuned4_full
```

### HF TRL minimum requirement run
```bash
python colab/run_openincident_hf_trl_minimal.py --task-id medium --env-mode stochastic --env-profile v2 --episodes 80 --warmup-episodes 20 --model-id sshleifer/tiny-gpt2 --output-dir artifacts/trl_loss_proof
```
"""

submission_links_md = f"""
## Final Submission Links (Copy-Paste)

### 1) Hugging Face Space URL for your Env
`{SPACE_HUB_URL}`

### 2) Training Run Notebook URL
`{COLAB_URL}`

### 3) YouTube demo video URL
`{YOUTUBE_URL}`

### Optional supporting links
- Blog MD (HF repo): `{BLOG_URL}`
- Full video script: `{SCRIPT_URL}`
- Live application (Vercel): `{APP_URL}`
- Space app URL: `{SPACE_APP_URL}`
- GitHub repository: `{GITHUB_URL}`
"""

css = """
:root {
  --panel-bg: linear-gradient(180deg, #121a2b, #0b1020);
  --text-main: #f2f7ff;
  --text-dim: #9fb4d0;
  --line: #27344f;
  --cyan: #00d4ff;
  --teal: #00e6b8;
  --orange: #ff9a3d;
}

body {
  background:
    radial-gradient(circle at 10% 10%, rgba(0, 212, 255, 0.15), transparent 35%),
    radial-gradient(circle at 90% 15%, rgba(0, 230, 184, 0.15), transparent 35%),
    #060913;
}

.hero {
  border: 1px solid var(--line);
  border-radius: 18px;
  background: linear-gradient(145deg, #0f1728, #081022);
  padding: 22px;
  margin-bottom: 10px;
  box-shadow: 0 15px 50px rgba(0, 0, 0, 0.35);
}
.hero h1 {
  margin: 6px 0 8px;
  font-size: 46px;
  line-height: 1.02;
  color: var(--text-main);
}
.hero-badge {
  display: inline-block;
  border: 1px solid #2e4a66;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  letter-spacing: 0.3px;
  color: #9fd7ff;
  background: rgba(0, 212, 255, 0.08);
}
.hero-sub {
  margin: 0;
  color: #c8d9f0;
  font-size: 16px;
}
.hero-story {
  margin: 12px 0 0;
  color: #a7bdd8;
  font-size: 15px;
  line-height: 1.5;
}
.hero-links {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.hero-links a {
  color: #0a0f1f;
  background: linear-gradient(135deg, var(--cyan), #81f0ff);
  text-decoration: none;
  border-radius: 10px;
  padding: 8px 12px;
  font-weight: 600;
  font-size: 13px;
}
.hero-links a:nth-child(2) {
  background: linear-gradient(135deg, var(--teal), #8fffe8);
}
.hero-links a:nth-child(3) {
  background: linear-gradient(135deg, var(--orange), #ffc784);
}
.kpi {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px;
  background: var(--panel-bg);
  min-height: 100px;
}
.kpi-title {
  color: #8ea6c6;
  font-size: 12px;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}
.kpi-value {
  color: var(--text-main);
  font-size: 38px;
  line-height: 1;
  font-weight: 700;
  margin-top: 8px;
}
.kpi-sub {
  color: #9ab0ce;
  margin-top: 6px;
  font-size: 13px;
}
.blue .kpi-value {
  color: #7cd5ff;
}
.green .kpi-value {
  color: #90ffd9;
}
.amber .kpi-value {
  color: #ffd59f;
}
.pink .kpi-value {
  color: #ffc4f2;
}
"""

with gr.Blocks(title="OpenIncident X", css=css) as demo:
    gr.HTML(hero_html)

    with gr.Row():
        gr.Markdown(
            kpi_card(
                "Success rate (v1 trained)",
                as_pct_compact(trained.get("success_rate", 0.0)),
                "Official judged packet",
                tone="blue",
            )
        )
        gr.Markdown(
            kpi_card(
                "Root-cause rate (v1 trained)",
                as_pct_compact(trained.get("root_cause_rate", 0.0)),
                "Diagnosis quality",
                tone="green",
            )
        )
        gr.Markdown(
            kpi_card(
                "Restore rate (v1 trained)",
                as_pct_compact(trained.get("restore_rate", 0.0)),
                "Service recovery",
                tone="amber",
            )
        )
        gr.Markdown(
            kpi_card(
                "Root-cause rate (v2 trained)",
                as_pct_compact(v2_trained.get("root_cause_rate", 0.0)),
                "Harder robustness profile",
                tone="pink",
            )
        )

    with gr.Tabs():
        with gr.TabItem("Mission & Story"):
            gr.Markdown(story_md)
            gr.Markdown(
                "### Product flow shown in demo\n"
                "Sign in -> Create project -> Run checks -> Open incident -> Triage -> Evidence-backed resolution"
            )

        with gr.TabItem("Judge Checklist"):
            gr.Markdown(requirements_md)

        with gr.TabItem("Results"):
            gr.Markdown(results_md)
            if plot_v1.exists():
                gr.Image(value=str(plot_v1), label="Reward curve (v1 official)")
            else:
                gr.Markdown(
                    "Reward plot missing at `artifacts/colab_demo_v1/medium_epsilon_rewards.png`."
                )
            if plot_v2.exists():
                gr.Image(value=str(plot_v2), label="Reward curve (v2 harder profile)")
            if plot_trl.exists():
                gr.Image(value=str(plot_trl), label="TRL loss curve (v2)")
            gr.Markdown("### Best successful trajectory (v1)")
            gr.Code(value=str(actions), language="json")

        with gr.TabItem("Reproducibility"):
            gr.Markdown(repro_md)
            if dataset_summary:
                gr.Markdown("### Dataset summary (HF TRL)")
                gr.JSON(value=dataset_summary)
            if trl_summary:
                gr.Markdown("### TRL training summary")
                gr.JSON(value=trl_summary)

        with gr.TabItem("Final Submission Links"):
            gr.Markdown(submission_links_md)

        with gr.TabItem("Raw Metrics"):
            gr.Markdown("### v1 metrics JSON")
            gr.JSON(value=v1)
            if v2:
                gr.Markdown("### v2 metrics JSON")
                gr.JSON(value=v2)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")))
