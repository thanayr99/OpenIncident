from __future__ import annotations

from pathlib import Path

from models import TestEnvironmentCommandResult
from server import test_environment as runner
from server.incident_workflow import validate_patch_proposal


VALID_PATCH = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-old
+new
"""


def test_patch_validator_accepts_small_text_diff() -> None:
    assert validate_patch_proposal(VALID_PATCH) == []


def test_patch_validator_rejects_traversal_and_secret_paths() -> None:
    traversal = VALID_PATCH.replace("a/app.py b/app.py", "a/../outside.py b/../outside.py")
    secrets = VALID_PATCH.replace("app.py", ".env.production")
    assert any("escape" in issue.lower() for issue in validate_patch_proposal(traversal))
    assert any("credential" in issue.lower() or "protected" in issue.lower() for issue in validate_patch_proposal(secrets))


def test_patch_validator_rejects_binary_and_symlink_diffs() -> None:
    assert any("Binary" in issue for issue in validate_patch_proposal(VALID_PATCH + "\nGIT binary patch\n"))
    assert any("Symlink" in issue for issue in validate_patch_proposal(VALID_PATCH + "\nnew file mode 120000\n"))


def test_patch_is_applied_to_disposable_copy_before_isolated_test_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "app.py").write_text("old\n", encoding="utf-8")
    seen: dict[str, object] = {}

    def fake_run(command, *, cwd, timeout_seconds=900.0, **kwargs):
        seen["command"] = command
        seen["cwd"] = str(cwd)
        seen["content"] = (Path(cwd) / "app.py").read_text(encoding="utf-8")
        return TestEnvironmentCommandResult(
            command=command,
            return_code=0,
            stdout="2 passed",
            stderr="",
            duration_seconds=0.5,
            success=True,
        )

    monkeypatch.setattr(runner, "run_shell_command", fake_run)
    result = runner.validate_patch_and_run_tests(
        workspace,
        VALID_PATCH,
        install_command="pip install -r requirements.txt",
        test_command="pytest -q",
    )

    assert result["success"] is True
    assert result["stage"] == "tests"
    assert seen["content"] == "new\n"
    assert Path(seen["cwd"]) != workspace
    assert (workspace / "app.py").read_text(encoding="utf-8") == "old\n"
    assert "pip install -r requirements.txt" in str(seen["command"])
    assert "pytest -q" in str(seen["command"])
