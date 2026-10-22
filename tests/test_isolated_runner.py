from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from server import test_environment as runner


def test_command_runner_uses_disposable_container_and_does_not_forward_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("OPENINCIDENT_TEST_RUNNER_NETWORK", "none")
    monkeypatch.setenv("SECRET_KEY", "host-secret-must-not-leak")
    monkeypatch.setenv("OPENINCIDENT_TEST_RUNNER_IMAGE", "openincident-test-runner:local")
    calls: list[dict[str, object]] = []

    def fake_run(args, **kwargs):  # noqa: ANN001
        calls.append({"args": args, **kwargs})
        return subprocess.CompletedProcess(args, 0, stdout="tests passed", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_shell_command(
        "npm test",
        cwd=workspace,
        env={"PROJECT_SECRET": "must-not-leak"},
        timeout_seconds=99999,
    )

    assert result.success
    assert result.stdout == "tests passed"
    assert len(calls) == 1
    args = calls[0]["args"]
    env = calls[0]["env"]
    assert isinstance(args, list)
    assert isinstance(env, dict)
    assert args[:2] == ["docker", "run"]
    assert args[args.index("--network") + 1] == "none"
    assert args[args.index("--memory") + 1] == "2g"
    assert args[args.index("--cpus") + 1] == "2"
    assert args[args.index("--pids-limit") + 1] == "256"
    assert args[args.index("--user") + 1] == "10001:10001"
    assert args[args.index("--read-only"):]  # root filesystem is read-only
    assert any("dst=/source,readonly" in item for item in args if isinstance(item, str))
    assert "host-secret-must-not-leak" not in str(env)
    assert "PROJECT_SECRET" not in str(env)
    assert calls[0]["timeout"] == 1800.0


def test_command_runner_rejects_unrecognized_network_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENINCIDENT_TEST_RUNNER_NETWORK", "host")

    with pytest.raises(ValueError, match="must be 'none' or 'bridge'"):
        runner.run_shell_command("pytest", cwd=tmp_path)
