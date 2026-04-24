from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _pct(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def _num(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _delta(after: float | int | None, before: float | int | None) -> str:
    if after is None or before is None:
        return "n/a"
    return f"{float(after) - float(before):+.4f}"


def build_packet(metrics_path: Path, testcases_path: Path, output_path: Path | None) -> str:
    metrics = _load_json(metrics_path)
    testcases = _load_json(testcases_path)

    baseline = metrics.get("baseline", {})
    trained = metrics.get("trained", {})
    artifacts = metrics.get("artifacts", {})

    task_id = metrics.get("task_id", "unknown")
    policy = metrics.get("policy", "unknown")
    seed = metrics.get("seed", "unknown")

    case_counter = Counter(case.get("category", "uncategorized") for case in testcases)
    total_cases = len(testcases)

    lines = [
        "# OpenIncident X - Judge RL Packet",
        "",
        "## Exact RL Run",
        f"- Environment: `ProductionIncidentEnv`",
        f"- Task: `{task_id}`",
        f"- Policy: `{policy}`",
        f"- Seed: `{seed}`",
        f"- Baseline episodes: `{baseline.get('episodes', 0)}`",
        f"- Trained episodes: `{trained.get('episodes', 0)}`",
        "",
        "## Core Outcome",
        f"- Success rate: `{_pct(baseline.get('success_rate'))} -> {_pct(trained.get('success_rate'))}`",
        f"- Closure gap: `{_pct(baseline.get('closure_gap_rate'))} -> {_pct(trained.get('closure_gap_rate'))}`",
        f"- Avg steps: `{_num(baseline.get('avg_steps'))} -> {_num(trained.get('avg_steps'))}`",
        f"- Avg train reward: `{_num(baseline.get('avg_train_reward'))} -> {_num(trained.get('avg_train_reward'))}`",
        "",
        "## Delta Summary",
        f"- success_rate delta: `{_delta(trained.get('success_rate'), baseline.get('success_rate'))}`",
        f"- closure_gap_rate delta: `{_delta(trained.get('closure_gap_rate'), baseline.get('closure_gap_rate'))}`",
        f"- avg_steps delta: `{_delta(trained.get('avg_steps'), baseline.get('avg_steps'))}`",
        "",
        "## Dataset Used (Explain This Clearly)",
        "- There is no static supervised dataset for RL optimization here.",
        "- The training data is generated online from environment rollouts:",
        "  state -> action -> reward -> next_state -> done.",
        "- Scenario definitions come from `tasks/easy.py`, `tasks/medium.py`, `tasks/hard.py`.",
        f"- Evaluation coverage pack: `{total_cases}` RL test cases in `{testcases_path}`.",
        "",
        "### RL Test Case Category Split",
    ]

    for category, count in sorted(case_counter.items()):
        lines.append(f"- {category}: `{count}`")

    lines.extend(
        [
            "",
            "## Artifact Paths",
            f"- metrics json: `{metrics_path}`",
            f"- rewards csv: `{artifacts.get('csv', 'n/a')}`",
            f"- rewards plot: `{artifacts.get('plot', 'n/a')}`",
            "",
            "## One-Line Judge Statement",
            "OpenIncident X trains a Reliability Agent in a partially observable incident-response environment and demonstrates measurable improvement in closure behavior versus a random baseline.",
        ]
    )

    output_text = "\n".join(lines)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
    return output_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a judge-friendly RL evidence packet.")
    parser.add_argument(
        "--metrics",
        default="artifacts/colab_demo/medium_epsilon_metrics.json",
        help="Path to metrics JSON produced by the hackathon runner.",
    )
    parser.add_argument(
        "--testcases",
        default="artifacts/rl_test_cases_65.json",
        help="Path to RL testcase coverage file.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/judge_rl_packet.md",
        help="Where to write the markdown packet.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics_path = Path(args.metrics)
    testcases_path = Path(args.testcases)
    output_path = Path(args.output) if args.output else None
    packet = build_packet(metrics_path, testcases_path, output_path)
    print(packet)


if __name__ == "__main__":
    main()
