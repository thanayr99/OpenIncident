from __future__ import annotations

from types import SimpleNamespace

import pytest

from server import patch_agent


VALID_DIFF = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-old
+new
"""


def test_patch_context_redacts_common_credentials() -> None:
    text = patch_agent._redact("Authorization: Bearer super-secret-token password=hunter2")
    assert "super-secret-token" not in text
    assert "hunter2" not in text
    assert "[REDACTED]" in text


def test_extract_diff_removes_markdown_fence() -> None:
    assert patch_agent._extract_diff("```diff\n" + VALID_DIFF + "\n```") == VALID_DIFF.strip()


def test_patch_generation_requires_provider_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(patch_agent.PatchDraftUnavailable):
        patch_agent.generate_patch_draft(query="fix", incident_summary="failure", logs=[], code_context=[{"path": "app.py", "snippet": "def f(): return 1"}])


def test_patch_generation_returns_only_a_validated_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponses:
        def create(self, **kwargs):
            assert kwargs["model"] == "test-model"
            return SimpleNamespace(output_text=VALID_DIFF)

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setattr(patch_agent, "OpenAI", FakeClient)
    patch, model = patch_agent.generate_patch_draft(
        query="fix app.py",
        incident_summary="failure in app.py",
        logs=[{"message": "Authorization: Bearer do-not-send-this"}],
        code_context=[{"path": "app.py", "snippet": "def f(): return 'old'"}],
    )
    assert patch == VALID_DIFF
    assert model == "test-model"


def test_patch_generation_rejects_paths_outside_supplied_context(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=VALID_DIFF.replace("app.py", "other.py"))

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setattr(patch_agent, "OpenAI", FakeClient)
    with pytest.raises(ValueError, match="outside the supplied repository context"):
        patch_agent.generate_patch_draft(
            query="fix app.py",
            incident_summary="failure in app.py",
            logs=[],
            code_context=[{"path": "app.py", "snippet": "def f(): return 'old'"}],
        )
