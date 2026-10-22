from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IncidentWorkflowStatus(str, Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    TESTING = "testing"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IncidentWorkflowEventRequest(BaseModel):
    status: IncidentWorkflowStatus
    agent_role: str = Field(min_length=1, max_length=80)
    event_type: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=2000)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class IncidentInvestigationRequest(BaseModel):
    query: str | None = Field(default=None, max_length=500)


class IncidentPatchProposalRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    patch: str = Field(min_length=1, max_length=100_000)


class IncidentWorkflowApprovalRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)


class IncidentWorkflowEvent(BaseModel):
    event_id: str
    project_id: str
    run_id: str
    status: IncidentWorkflowStatus
    agent_role: str
    event_type: str
    summary: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


ALLOWED_TRANSITIONS: dict[IncidentWorkflowStatus | None, set[IncidentWorkflowStatus]] = {
    None: {IncidentWorkflowStatus.DETECTED},
    IncidentWorkflowStatus.DETECTED: {IncidentWorkflowStatus.INVESTIGATING, IncidentWorkflowStatus.FAILED, IncidentWorkflowStatus.CANCELLED},
    IncidentWorkflowStatus.INVESTIGATING: {IncidentWorkflowStatus.INVESTIGATING, IncidentWorkflowStatus.TESTING, IncidentWorkflowStatus.FAILED, IncidentWorkflowStatus.CANCELLED},
    IncidentWorkflowStatus.TESTING: {IncidentWorkflowStatus.INVESTIGATING, IncidentWorkflowStatus.AWAITING_APPROVAL, IncidentWorkflowStatus.FAILED, IncidentWorkflowStatus.CANCELLED},
    IncidentWorkflowStatus.AWAITING_APPROVAL: {IncidentWorkflowStatus.INVESTIGATING, IncidentWorkflowStatus.RESOLVED, IncidentWorkflowStatus.CANCELLED},
    IncidentWorkflowStatus.FAILED: {IncidentWorkflowStatus.INVESTIGATING, IncidentWorkflowStatus.CANCELLED},
    IncidentWorkflowStatus.RESOLVED: set(),
    IncidentWorkflowStatus.CANCELLED: set(),
}


def validate_patch_proposal(patch: str) -> list[str]:
    """Reject malformed diffs and unsafe paths before sandbox execution."""
    import posixpath

    issues: list[str] = []
    if len(patch) > 100_000:
        return ["Patch exceeds the 100 KB limit."]
    if chr(0) in patch:
        return ["Patch contains a NUL byte."]
    if "GIT binary patch" in patch or "Binary files " in patch:
        issues.append("Binary patches are not supported; propose text changes only.")
    if "new file mode 120000" in patch or "old mode 120000" in patch or "new file mode 160000" in patch or "old mode 160000" in patch:
        issues.append("Symlink and submodule changes are not allowed in patch proposals.")

    paths: set[str] = set()
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) != 4 or not parts[2].startswith("a/") or not parts[3].startswith("b/"):
                issues.append("Diff headers must use simple relative paths without whitespace.")
                continue
            paths.add(parts[2][2:])
            paths.add(parts[3][2:])
        elif line.startswith("--- ") or line.startswith("+++ "):
            path = line[4:].split(chr(9), 1)[0]
            if path == "/dev/null":
                continue
            if path.startswith("a/") or path.startswith("b/"):
                path = path[2:]
            if not path or path.startswith("/") or chr(92) in path:
                issues.append("Patch paths must be relative POSIX paths.")
                continue
            normalized = posixpath.normpath(path)
            if normalized in {".", ".."} or normalized.startswith("../"):
                issues.append("Patch paths cannot escape the repository workspace.")
                continue
            paths.add(normalized)

    if not paths:
        issues.append("Patch does not contain any recognized file changes.")
    if len(paths) > 40:
        issues.append("A single proposal may change at most 20 files.")
    forbidden_parts = {".git", ".env", ".ssh", "node_modules", ".venv", "venv"}
    forbidden_names = {".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials.json", "service-account.json", "secrets.json"}
    for path in paths:
        parts = {part.lower() for part in path.split("/")}
        name = path.rsplit("/", 1)[-1].lower()
        if parts & forbidden_parts or name in forbidden_names or name.startswith(".env") or name.endswith((".pem", ".key", ".p12", ".pfx", ".secret")):
            issues.append("Patch touches a protected or credential-related path.")
    if not any(line.startswith("@@ ") for line in patch.splitlines()):
        issues.append("Patch must contain at least one text hunk.")
    return list(dict.fromkeys(issues))
