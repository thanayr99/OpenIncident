from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from models import (
    EnvironmentWorkspaceInsight,
    TestEnvironmentCommandResult,
    TestEnvironmentConfig,
    TestEnvironmentRunRequest,
    TestEnvironmentRunResult,
)
from server.github_repo import discover_frontend_surface_from_workspace


def inspect_workspace(
    project_id: str,
    repository_url: str,
    workspace_path: str | Path,
) -> EnvironmentWorkspaceInsight:
    workspace = Path(workspace_path)
    if not workspace.exists():
        return EnvironmentWorkspaceInsight(
            workspace_path=str(workspace),
            notes=[f"Workspace does not exist: {workspace}"],
        )

    detected_files: list[str] = []
    for name in (
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "package-lock.json",
        "requirements.txt",
        "pyproject.toml",
        "pytest.ini",
        "vite.config.js",
        "vite.config.ts",
        "next.config.js",
        "next.config.mjs",
        "next.config.ts",
    ):
        if (workspace / name).exists():
            detected_files.append(name)

    package_manager = None
    if (workspace / "pnpm-lock.yaml").exists():
        package_manager = "pnpm"
    elif (workspace / "yarn.lock").exists():
        package_manager = "yarn"
    elif (workspace / "package-lock.json").exists() or (workspace / "package.json").exists():
        package_manager = "npm"

    install_command = None
    test_command = None
    recommended_workdir = None
    notes: list[str] = []

    package_json = workspace / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
            notes.append("package.json exists but could not be parsed.")

        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        install_command = {
            "pnpm": "pnpm install",
            "yarn": "yarn install",
            "npm": "npm install",
        }.get(package_manager or "npm", "npm install")

        if "test" in scripts:
            if package_manager == "pnpm":
                test_command = "pnpm test"
            elif package_manager == "yarn":
                test_command = "yarn test"
            else:
                test_command = "npm test"
        elif "lint" in scripts:
            if package_manager == "pnpm":
                test_command = "pnpm lint"
            elif package_manager == "yarn":
                test_command = "yarn lint"
            else:
                test_command = "npm run lint"
            notes.append("No test script detected; lint command suggested as a fallback validation step.")

    if test_command is None and (workspace / "pyproject.toml").exists():
        install_command = install_command or "pip install -e ."
        test_command = "pytest"
    elif test_command is None and (workspace / "requirements.txt").exists():
        install_command = install_command or "pip install -r requirements.txt"
        test_command = "pytest"

    class _RepoProject:
        def __init__(self, project_id_value: str, repository_url_value: str) -> None:
            self.project_id = project_id_value
            self.repository_url = repository_url_value

    discovery = discover_frontend_surface_from_workspace(
        _RepoProject(project_id, repository_url),
        workspace,
    )
    if discovery.app_root:
        recommended_workdir = discovery.app_root

    if discovery.framework:
        notes.append(f"Detected frontend framework: {discovery.framework}.")
    if not discovery.routes:
        notes.append("No frontend routes detected yet; this project may be API-only or use an unsupported layout.")

    return EnvironmentWorkspaceInsight(
        workspace_path=str(workspace),
        framework=discovery.framework,
        app_root=discovery.app_root,
        package_manager=package_manager,
        detected_files=detected_files,
        recommended_install_command=install_command,
        recommended_test_command=test_command,
        recommended_workdir=recommended_workdir,
        route_count=len(discovery.routes),
        notes=notes,
    )


def _repo_dir_name(project_id: str) -> str:
    return f"{project_id}-repo"


def prepare_workspace(
    config: TestEnvironmentConfig,
    *,
    base_dir: str | Path = "data/test_envs",
    pull_latest: bool = True,
    timeout_seconds: float = 300.0,
) -> Path:
    root = Path(base_dir)
    root.mkdir(parents=True, exist_ok=True)
    workspace = (root / _repo_dir_name(config.project_id)).resolve()
    repo_source = config.repository_url
    local_repo = Path(config.repository_url)
    is_local_repo = local_repo.exists()
    if is_local_repo:
        repo_source = str(local_repo.resolve())

    if not workspace.exists():
        if is_local_repo and local_repo.is_dir():
            shutil.copytree(local_repo.resolve(), workspace, dirs_exist_ok=False)
        else:
            clone_command = ["git", "clone"]
            if config.branch:
                clone_command.extend(["--branch", config.branch])
            clone_command.extend([repo_source, str(workspace)])
            subprocess.run(clone_command, check=True, capture_output=True, text=True, timeout=timeout_seconds)
    elif pull_latest:
        if is_local_repo and local_repo.is_dir():
            shutil.rmtree(workspace, ignore_errors=True)
            shutil.copytree(local_repo.resolve(), workspace, dirs_exist_ok=False)
        else:
            subprocess.run(["git", "-C", str(workspace), "fetch", "--all"], check=True, capture_output=True, text=True, timeout=timeout_seconds)
            target = config.branch or "HEAD"
            subprocess.run(["git", "-C", str(workspace), "checkout", target], check=True, capture_output=True, text=True, timeout=timeout_seconds)
            subprocess.run(["git", "-C", str(workspace), "pull", "--ff-only"], check=True, capture_output=True, text=True, timeout=timeout_seconds)

    if config.workdir:
        return workspace / config.workdir
    return workspace


def run_shell_command(
    command: str,
    *,
    cwd: str | Path,
    env: dict[str, str] | None = None,
    shell_name: str = "powershell",
    timeout_seconds: float = 900.0,
) -> TestEnvironmentCommandResult:
    started_at = perf_counter()
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    if shell_name.lower() == "cmd":
        invocation = ["cmd.exe", "/c", command]
    else:
        invocation = ["powershell.exe", "-Command", command]

    completed = subprocess.run(
        invocation,
        cwd=str(cwd),
        env=merged_env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    duration = perf_counter() - started_at
    return TestEnvironmentCommandResult(
        command=command,
        return_code=completed.returncode,
        stdout=completed.stdout[-12000:],
        stderr=completed.stderr[-12000:],
        duration_seconds=round(duration, 3),
        success=completed.returncode == 0,
    )


def run_test_environment(
    config: TestEnvironmentConfig,
    request: TestEnvironmentRunRequest,
    *,
    base_dir: str | Path = "data/test_envs",
) -> TestEnvironmentRunResult:
    started_at = datetime.now(timezone.utc)
    workspace = prepare_workspace(
        config,
        base_dir=base_dir,
        pull_latest=request.pull_latest,
        timeout_seconds=min(request.timeout_seconds, 300.0),
    )

    install_result = None
    test_result = None
    summary = "Testing environment completed."
    success = True

    install_command = request.install_command_override or config.install_command
    test_command = request.test_command_override or config.test_command

    if request.run_install and install_command:
        install_result = run_shell_command(
            install_command,
            cwd=workspace,
            env=config.env,
            shell_name=config.shell,
            timeout_seconds=request.timeout_seconds,
        )
        success = success and install_result.success
        if not install_result.success:
            summary = "Repository pull succeeded, but install/setup failed in the testing environment."

    if request.run_tests and test_command and success:
        test_result = run_shell_command(
            test_command,
            cwd=workspace,
            env=config.env,
            shell_name=config.shell,
            timeout_seconds=request.timeout_seconds,
        )
        success = success and test_result.success
        summary = (
            "Repository tests passed in the testing environment."
            if success
            else "Repository tests failed in the testing environment."
        )

    completed_at = datetime.now(timezone.utc)
    return TestEnvironmentRunResult(
        project_id=config.project_id,
        repository_url=config.repository_url,
        branch=config.branch,
        workspace_path=str(workspace),
        pull_latest=request.pull_latest,
        run_install=request.run_install,
        run_tests=request.run_tests,
        install_result=install_result,
        test_result=test_result,
        success=success,
        summary=summary,
        started_at=started_at,
        completed_at=completed_at,
    )
