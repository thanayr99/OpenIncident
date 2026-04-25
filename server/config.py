from __future__ import annotations

import os
from pathlib import Path


def _load_backend_env_file() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env.backend"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_backend_env_file()


def get_allowed_origins() -> list[str]:
    configured = os.getenv("OPENINCIDENT_ALLOWED_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://open-incident.vercel.app",
    ]


def get_allowed_origin_regex() -> str | None:
    configured = os.getenv("OPENINCIDENT_ALLOWED_ORIGIN_REGEX", "").strip()
    if configured:
        return configured
    allow_vercel_previews = os.getenv("OPENINCIDENT_ALLOW_VERCEL_PREVIEWS", "true").strip().lower()
    if allow_vercel_previews in {"1", "true", "yes", "on"}:
        return r"^https://.*\.vercel\.app$"
    return None


def get_database_url() -> str:
    database_url = os.getenv("OPENINCIDENT_DATABASE_URL", "sqlite:///data/openincident.db").strip()
    placeholder_tokens = ("USERNAME", "PASSWORD", "HOST", "DATABASE")
    if not database_url or any(token in database_url for token in placeholder_tokens):
        return "sqlite:///data/openincident.db"
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


def get_database_target() -> str:
    database_url = get_database_url()
    if (
        database_url.startswith("postgresql://")
        or database_url.startswith("postgres://")
        or database_url.startswith("postgresql+psycopg://")
    ):
        return "neon-postgres"
    return "local-sqlite-fallback"


def get_api_port() -> int:
    return int(os.getenv("PORT", "8000"))
