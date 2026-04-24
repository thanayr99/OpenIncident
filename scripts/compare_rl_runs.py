from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _num(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _delta(new_value: float | None, old_value: float | None) -> float | None:
    if new_value is None or old_value is None:
        return None
    return round(new_value - old_value, 4)


def _extract_trained(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return metrics.get("trained", {})


def build_comparison(old_metrics: Dict[str, Any], new_metrics: Dict[str, Any]) -> Dict[str, Any]:
    old_trained = _extract_trained(old_metrics)
    new_trained = _extract_trained(new_metrics)

    fields = [
        "success_rate",
        "root_cause_rate",
        "restore_rate",
        "closure_gap_rate",
        "avg_env_reward",
        "avg_train_reward",
        "avg_steps",
    ]

    deltas = {
        field: _delta(
            float(new_trained[field]) if field in new_trained else None,
            float(old_trained[field]) if field in old_trained else None,
        )
        for field in fields
    }

    return {
        "task_id": new_metrics.get("task_id") or old_metrics.get("task_id"),
        "policy": new_metrics.get("policy") or old_metrics.get("policy"),
        "old_metrics_path": old_metrics.get("artifacts", {}).get("metrics"),
        "new_metrics_path": new_metrics.get("artifacts", {}).get("metrics"),
        "old": old_trained,
        "new": new_trained,
        "delta": deltas,
    }


def render_markdown(comparison: Dict[str, Any], old_label: str, new_label: str) -> str:
    old_block = comparison.get("old", {})
    new_block = comparison.get("new", {})
    delta = comparison.get("delta", {})

    lines = [
        "# RL Comparison - Before vs Tuned",
        "",
        f"- Task: `{comparison.get('task_id', 'unknown')}`",
        f"- Policy: `{comparison.get('policy', 'unknown')}`",
        f"- Old run: `{old_label}`",
        f"- New run: `{new_label}`",
        "",
        "## Key Metrics",
        f"- Success rate: `{_pct(old_block.get('success_rate'))} -> {_pct(new_block.get('success_rate'))}` (delta `{_num(delta.get('success_rate'))}`)",
        f"- Closure gap rate: `{_pct(old_block.get('closure_gap_rate'))} -> {_pct(new_block.get('closure_gap_rate'))}` (delta `{_num(delta.get('closure_gap_rate'))}`)",
        f"- Root-cause rate: `{_pct(old_block.get('root_cause_rate'))} -> {_pct(new_block.get('root_cause_rate'))}` (delta `{_num(delta.get('root_cause_rate'))}`)",
        f"- Restore rate: `{_pct(old_block.get('restore_rate'))} -> {_pct(new_block.get('restore_rate'))}` (delta `{_num(delta.get('restore_rate'))}`)",
        f"- Avg train reward: `{_num(old_block.get('avg_train_reward'))} -> {_num(new_block.get('avg_train_reward'))}` (delta `{_num(delta.get('avg_train_reward'))}`)",
        f"- Avg env reward: `{_num(old_block.get('avg_env_reward'))} -> {_num(new_block.get('avg_env_reward'))}` (delta `{_num(delta.get('avg_env_reward'))}`)",
        f"- Avg steps: `{_num(old_block.get('avg_steps'))} -> {_num(new_block.get('avg_steps'))}` (delta `{_num(delta.get('avg_steps'))}`)",
        "",
        "## Interpretation",
        "- The tuned run emphasizes full closure behavior (diagnose + restore + resolve) instead of lingering in partial mitigation states.",
        "- This benchmark is simulation-rollout RL data, not a static real-world supervised dataset.",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two RL metrics JSON runs.")
    parser.add_argument("--old", required=True, help="Path to old metrics JSON.")
    parser.add_argument("--new", required=True, help="Path to new metrics JSON.")
    parser.add_argument("--json-out", required=True, help="Output JSON path.")
    parser.add_argument("--md-out", required=True, help="Output markdown path.")
    parser.add_argument("--old-label", default="previous")
    parser.add_argument("--new-label", default="tuned")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    old_path = Path(args.old)
    new_path = Path(args.new)
    json_out = Path(args.json_out)
    md_out = Path(args.md_out)

    old_metrics = _load(old_path)
    new_metrics = _load(new_path)
    comparison = build_comparison(old_metrics, new_metrics)
    markdown = render_markdown(comparison, args.old_label, args.new_label)

    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    md_out.write_text(markdown, encoding="utf-8")

    print(f"Saved JSON comparison to {json_out}")
    print(f"Saved markdown comparison to {md_out}")


if __name__ == "__main__":
    main()
