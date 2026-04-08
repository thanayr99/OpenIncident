from __future__ import annotations

import ast
import json
import sys
import time
import traceback
from typing import Any, Dict, List

SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def run_test_cases(function: Any, test_cases: List[Dict[str, Any]]) -> tuple[int, int, List[str]]:
    passed = 0
    failures: List[str] = []
    for test_case in test_cases:
        try:
            actual = function(**test_case["input_data"])
            if actual == test_case["expected_output"]:
                passed += 1
            else:
                failures.append(
                    f"{test_case['description']}: expected {test_case['expected_output']!r}, got {actual!r}"
                )
        except Exception as exc:
            failures.append(f"{test_case['description']}: raised {exc.__class__.__name__}: {exc}")
    return passed, len(test_cases) - passed, failures


def benchmark_function(function: Any, test_cases: List[Dict[str, Any]], repetitions: int) -> float:
    if not test_cases:
        return 0.0

    started_at = time.perf_counter()
    for _ in range(max(repetitions, 1)):
        for test_case in test_cases:
            function(**test_case["input_data"])
    duration_ms = (time.perf_counter() - started_at) * 1000.0
    total_calls = max(repetitions, 1) * len(test_cases)
    return duration_ms / total_calls


def main() -> None:
    payload = json.loads(sys.stdin.read())
    code_snippet = payload["code_snippet"]
    entry_point = payload["entry_point"]
    visible_tests = payload["visible_tests"]
    hidden_tests = payload["hidden_tests"]
    benchmark_repetitions = payload["benchmark_repetitions"]

    try:
        ast.parse(code_snippet)
    except SyntaxError as exc:
        print(
            json.dumps(
                {
                    "syntax_error": f"SyntaxError: {exc.msg} (line {exc.lineno})",
                    "visible_passed": 0,
                    "visible_failed": len(visible_tests),
                    "hidden_passed": 0,
                    "hidden_failed": len(hidden_tests),
                    "failure_messages": [f"syntax error: {exc.msg}"],
                    "hidden_failure_messages": [],
                    "benchmark_time_ms": None,
                }
            )
        )
        return

    namespace: Dict[str, Any] = {"__builtins__": SAFE_BUILTINS.copy()}

    try:
        exec(code_snippet, namespace, namespace)
    except Exception:
        print(
            json.dumps(
                {
                    "syntax_error": None,
                    "visible_passed": 0,
                    "visible_failed": len(visible_tests),
                    "hidden_passed": 0,
                    "hidden_failed": len(hidden_tests),
                    "failure_messages": [traceback.format_exc(limit=1).strip()],
                    "hidden_failure_messages": [],
                    "benchmark_time_ms": None,
                }
            )
        )
        return

    function = namespace.get(entry_point)
    if not callable(function):
        print(
            json.dumps(
                {
                    "syntax_error": None,
                    "visible_passed": 0,
                    "visible_failed": len(visible_tests),
                    "hidden_passed": 0,
                    "hidden_failed": len(hidden_tests),
                    "failure_messages": [f"Entry point '{entry_point}' is missing or not callable"],
                    "hidden_failure_messages": [],
                    "benchmark_time_ms": None,
                }
            )
        )
        return

    visible_passed, visible_failed, visible_failures = run_test_cases(function, visible_tests)
    hidden_passed, hidden_failed, hidden_failures = run_test_cases(function, hidden_tests)

    benchmark_time_ms = None
    try:
        benchmark_time_ms = benchmark_function(function, visible_tests or hidden_tests, benchmark_repetitions)
    except Exception as exc:
        visible_failures.append(f"benchmark failed: {exc.__class__.__name__}: {exc}")

    print(
        json.dumps(
            {
                "syntax_error": None,
                "visible_passed": visible_passed,
                "visible_failed": visible_failed,
                "hidden_passed": hidden_passed,
                "hidden_failed": hidden_failed,
                "failure_messages": visible_failures,
                "hidden_failure_messages": hidden_failures,
                "benchmark_time_ms": benchmark_time_ms,
            }
        )
    )


if __name__ == "__main__":
    main()

