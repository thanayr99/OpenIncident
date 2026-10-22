from __future__ import annotations

import os
import re
from typing import Any

from openai import OpenAI

from server.incident_workflow import validate_patch_proposal


class PatchDraftUnavailable(RuntimeError):
    pass


def _redact(text: str) -> str:
    patterns = [
        (re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+"), r"\1[REDACTED]"),
        (re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|hf_token|database_url|client_secret|private[_-]?key)(?:\s*[:=]\s*))[^^\s,;]+"), r"\1[REDACTED]"),
        (re.compile(r"(?i)(postgres(?:ql)?://[^:\s]+:)[^@\s]+(@)"), r"\1[REDACTED]\2"),
        (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    ]
    result = text
    for pattern, replacement in patterns:
        result = pattern.sub(replacement, result)
    result = re.sub(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", "[REDACTED_PRIVATE_KEY]", result, flags=re.DOTALL)
    return result[:4000]


def _extract_diff(output: str) -> str:
    text = output.strip()
    if text.startswith("```"):
        parts = text.split("```")
        candidates = [part.strip() for part in parts if "diff --git " in part]
        if candidates:
            text = candidates[0]
            if text.startswith("diff --git "):
                return text
            first_newline = text.find("\n")
            if first_newline >= 0 and text[:first_newline].strip().lower() in {"diff", "patch"}:
                text = text[first_newline + 1:]
    start = text.find("diff --git ")
    return text[start:].strip() if start >= 0 else ""


def generate_patch_draft(
    *,
    query: str,
    incident_summary: str,
    logs: list[dict[str, Any]],
    code_context: list[dict[str, str]],
) -> tuple[str, str]:
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        raise PatchDraftUnavailable("Patch drafting is not configured. Set HF_TOKEN on the server or paste a diff manually.")

    base_url = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
    model = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
    client = OpenAI(api_key=token, base_url=base_url, timeout=60.0, max_retries=1)
    safe_logs = [_redact(str(item)) for item in logs[:10]]
    safe_context = [
        {"path": item.get("path", "")[:240], "snippet": _redact(item.get("snippet", ""))[:5000]}
        for item in code_context[:8]
        if item.get("path") and item.get("snippet")
    ]
    if not safe_context:
        raise ValueError("No repository code snippets were available; inspect the repository before generating a patch.")

    completion = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a cautious software repair engineer. Return ONLY a unified text diff with git headers "
                    "(diff --git a/path b/path). Do not include markdown fences or explanations. "
                    "Only edit files shown in the supplied code context. Never touch secrets, credentials, deployment "
                    "configuration, dependency lockfiles, or CI permissions. Keep the patch minimal. Do not claim tests passed."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Incident summary: {incident_summary[:2000]}\n"
                    f"Investigation query: {query[:500]}\n"
                    f"Sanitized recent logs: {safe_logs}\n"
                    f"Repository code context: {safe_context}\n"
                    "Propose a minimal patch that addresses the evidence. If the evidence is insufficient, return no diff."
                ),
            },
        ],
    )
    patch = _extract_diff(completion.output_text or "")
    if not patch:
        raise ValueError("The model did not return a unified diff. Add more repository evidence or write the patch manually.")
    issues = validate_patch_proposal(patch)
    if issues:
        raise ValueError("Generated patch rejected by safety validation: " + " ".join(issues))
    return patch, model
