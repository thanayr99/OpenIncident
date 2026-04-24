from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from models import (
    FrontendRouteCandidate,
    FrontendStoryTestPlan,
    FrontendSurfaceDiscovery,
    ProjectConfig,
    RepoCodeMatch,
    RepoInspectionResult,
    UserStoryRecord,
)


GITHUB_API = "https://api.github.com"


def parse_github_repo_url(repository_url: str) -> tuple[str, str] | None:
    if not repository_url:
        return None
    parsed = urlparse(repository_url)
    if "github.com" not in parsed.netloc.lower():
        return None
    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(path_parts) < 2:
        return None
    owner = path_parts[0]
    repo = path_parts[1].removesuffix(".git")
    return owner, repo


def _repo_headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": "OpenIncidentX",
    }


def fetch_repo_metadata(owner: str, repo: str) -> dict[str, Any]:
    response = requests.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=_repo_headers(), timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_repo_tree(owner: str, repo: str, branch: str) -> list[dict[str, Any]]:
    response = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
        headers=_repo_headers(),
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("tree", [])


def fetch_file_snippet(owner: str, repo: str, branch: str, path: str) -> str | None:
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    response = requests.get(raw_url, headers={"User-Agent": "OpenIncidentX"}, timeout=15)
    if not response.ok or not response.text:
        return None
    return response.text[:1200]


def build_story_query(story: UserStoryRecord) -> str:
    parts = [story.title, story.description, *story.acceptance_criteria, *story.tags]
    if story.hints.path:
        parts.append(story.hints.path)
    if story.hints.api_path:
        parts.append(story.hints.api_path)
    return " ".join(part for part in parts if part)


def _keywords_from_query(query: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", query.lower())
    stopwords = {
        "user",
        "should",
        "able",
        "when",
        "with",
        "from",
        "that",
        "this",
        "into",
        "after",
        "before",
        "page",
        "data",
        "story",
        "project",
        "save",
        "latest",
    }
    unique: list[str] = []
    for word in words:
        if word in stopwords:
            continue
        if word not in unique:
            unique.append(word)
    return unique[:12]


def _score_path(path: str, keywords: list[str]) -> tuple[float, list[str]]:
    lowered = path.lower()
    score = 0.0
    reasons: list[str] = []
    for keyword in keywords:
        if keyword in lowered:
            score += 2.0
            reasons.append(f"matched '{keyword}'")

    if lowered.endswith((".tsx", ".ts", ".jsx", ".js", ".py")):
        score += 0.5
    if "/api/" in lowered or lowered.startswith("api/"):
        score += 1.2
    if any(segment in lowered for segment in ("/components/", "/pages/", "/app/", "/src/")):
        score += 0.8
    return score, reasons


def inspect_repository_for_query(project: ProjectConfig, query: str) -> RepoInspectionResult:
    if not project.repository_url:
        return RepoInspectionResult(
            project_id=project.project_id,
            repository_url="",
            query=query,
            error_message="Project does not have a repository_url configured.",
        )

    parsed = parse_github_repo_url(project.repository_url)
    if not parsed:
        return RepoInspectionResult(
            project_id=project.project_id,
            repository_url=project.repository_url,
            query=query,
            error_message="Only public GitHub repository URLs are supported right now.",
        )

    owner, repo = parsed
    try:
        metadata = fetch_repo_metadata(owner, repo)
        branch = metadata.get("default_branch", "main")
        tree = fetch_repo_tree(owner, repo, branch)
    except requests.RequestException as exc:
        return RepoInspectionResult(
            project_id=project.project_id,
            repository_url=project.repository_url,
            query=query,
            error_message=str(exc),
        )

    keywords = _keywords_from_query(query)
    candidates: list[tuple[float, str, list[str]]] = []
    for node in tree:
        if node.get("type") != "blob":
            continue
        path = node.get("path", "")
        score, reasons = _score_path(path, keywords)
        if score > 0:
            candidates.append((score, path, reasons))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    matches: list[RepoCodeMatch] = []
    for score, path, reasons in candidates[:5]:
        snippet = fetch_file_snippet(owner, repo, branch, path)
        matches.append(
            RepoCodeMatch(
                path=path,
                score=round(score, 2),
                reason=", ".join(reasons) if reasons else "matched repository structure",
                snippet=snippet,
            )
        )

    return RepoInspectionResult(
        project_id=project.project_id,
        repository_url=project.repository_url,
        query=query,
        default_branch=branch,
        matches=matches,
    )


def inspect_repository_for_story(project: ProjectConfig, story: UserStoryRecord) -> RepoInspectionResult:
    return inspect_repository_for_query(project, build_story_query(story))


def _detect_framework(paths: list[str]) -> tuple[str | None, str | None]:
    lowered = [path.lower() for path in paths]
    if any(path.startswith("app/") or "/app/" in path for path in lowered):
        return "nextjs-app-router", "app"
    if any(path.startswith("pages/") or "/pages/" in path for path in lowered):
        return "nextjs-pages-router", "pages"
    if any(path.startswith("src/app/") for path in lowered):
        return "nextjs-app-router", "src/app"
    if any(path.startswith("src/pages/") for path in lowered):
        return "react-pages", "src/pages"
    if any(path.endswith(("app.tsx", "app.jsx")) for path in lowered):
        return "react-spa", "src"
    return None, None


def _normalize_route(route: str) -> str:
    route = route.replace("\\", "/")
    route = re.sub(r"/{2,}", "/", route)
    if not route.startswith("/"):
        route = f"/{route}"
    if route != "/" and route.endswith("/"):
        route = route[:-1]
    return route


def _route_from_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    lowered = normalized.lower()
    if "/api/" in lowered or lowered.startswith("pages/api/") or lowered.startswith("app/api/") or lowered.startswith("src/pages/api/"):
        return None

    route = None
    if lowered.startswith("app/") or lowered.startswith("src/app/"):
        base = normalized.split("app/", 1)[1] if "app/" in normalized else normalized.split("src/app/", 1)[1]
        if not re.search(r"/page\.(tsx|jsx|ts|js)$", base, re.IGNORECASE):
            return None
        route = re.sub(r"/page\.(tsx|jsx|ts|js)$", "", base, flags=re.IGNORECASE)
    elif lowered.startswith("pages/") or lowered.startswith("src/pages/"):
        base = normalized.split("pages/", 1)[1] if "pages/" in normalized else normalized.split("src/pages/", 1)[1]
        if not re.search(r"\.(tsx|jsx|ts|js)$", base, re.IGNORECASE):
            return None
        route = re.sub(r"\.(tsx|jsx|ts|js)$", "", base, flags=re.IGNORECASE)
        route = re.sub(r"/index$", "", route, flags=re.IGNORECASE)
        route = re.sub(r"^index$", "", route, flags=re.IGNORECASE)
    if route is None:
        return None
    route = route.replace("[...", "*").replace("[", ":").replace("]", "")
    return _normalize_route(route or "/")


def _discover_frontend_surface_from_paths(
    *,
    project: ProjectConfig,
    repository_url: str,
    paths: list[str],
) -> FrontendSurfaceDiscovery:
    framework, app_root = _detect_framework(paths)
    routes: list[FrontendRouteCandidate] = []
    for path in paths:
        route = _route_from_path(path)
        if route is None:
            continue
        score = 1.0
        lowered = path.lower()
        if route == "/":
            score += 0.8
        if any(keyword in lowered for keyword in ("login", "signin", "register", "signup", "dashboard", "profile", "home")):
            score += 0.6
        routes.append(
            FrontendRouteCandidate(
                route=route,
                source_path=path,
                route_type="page",
                score=round(score, 2),
            )
        )

    deduped: dict[str, FrontendRouteCandidate] = {}
    for item in routes:
        previous = deduped.get(item.route)
        if previous is None or item.score > previous.score:
            deduped[item.route] = item

    ordered = sorted(deduped.values(), key=lambda item: (-item.score, item.route))
    return FrontendSurfaceDiscovery(
        project_id=project.project_id,
        repository_url=repository_url,
        framework=framework,
        app_root=app_root,
        routes=ordered[:25],
    )


def discover_frontend_surface_from_workspace(project: ProjectConfig, workspace_path: str | Path) -> FrontendSurfaceDiscovery:
    workspace = Path(workspace_path)
    if not workspace.exists():
        return FrontendSurfaceDiscovery(
            project_id=project.project_id,
            repository_url=str(workspace),
            error_message=f"Workspace path does not exist: {workspace}",
        )

    paths: list[str] = []
    ignore_dirs = {".git", "node_modules", ".next", "dist", "build", "__pycache__"}
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [item for item in dirs if item not in ignore_dirs]
        for name in files:
            rel = Path(root, name).resolve().relative_to(workspace.resolve())
            paths.append(str(rel).replace("\\", "/"))

    return _discover_frontend_surface_from_paths(
        project=project,
        repository_url=str(workspace),
        paths=paths,
    )


def discover_frontend_surface(project: ProjectConfig, workspace_path: str | Path | None = None) -> FrontendSurfaceDiscovery:
    if workspace_path is not None:
        return discover_frontend_surface_from_workspace(project, workspace_path)

    if not project.repository_url:
        return FrontendSurfaceDiscovery(
            project_id=project.project_id,
            repository_url="",
            error_message="Project does not have a repository_url configured.",
        )

    parsed = parse_github_repo_url(project.repository_url)
    if not parsed:
        return FrontendSurfaceDiscovery(
            project_id=project.project_id,
            repository_url=project.repository_url,
            error_message="Only public GitHub repository URLs are supported right now.",
        )

    owner, repo = parsed
    try:
        metadata = fetch_repo_metadata(owner, repo)
        branch = metadata.get("default_branch", "main")
        tree = fetch_repo_tree(owner, repo, branch)
    except requests.RequestException as exc:
        return FrontendSurfaceDiscovery(
            project_id=project.project_id,
            repository_url=project.repository_url,
            error_message=str(exc),
        )

    paths = [node.get("path", "") for node in tree if node.get("type") == "blob"]
    return _discover_frontend_surface_from_paths(
        project=project,
        repository_url=project.repository_url,
        paths=paths,
    )


def _story_keywords(story: UserStoryRecord) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", build_story_query(story).lower())
    stop = {"user", "should", "page", "screen", "visible", "return", "valid", "data", "story"}
    unique: list[str] = []
    for token in tokens:
        if token in stop or token in unique:
            continue
        unique.append(token)
    return unique[:10]


def _score_route_for_story(route: str, story: UserStoryRecord) -> float:
    if story.hints.path and _normalize_route(story.hints.path) == route:
        return 10.0
    score = 0.0
    lowered = route.lower()
    for keyword in _story_keywords(story):
        if keyword in lowered:
            score += 2.0
    if any(keyword in lowered for keyword in ("login", "signin")) and any(
        word in build_story_query(story).lower() for word in ("login", "sign in", "signin")
    ):
        score += 3.0
    if any(keyword in lowered for keyword in ("register", "signup", "sign-up")) and any(
        word in build_story_query(story).lower() for word in ("register", "sign up", "signup")
    ):
        score += 3.0
    if route == "/":
        score += 0.5
    return score


def _infer_expected_text(story: UserStoryRecord) -> str | None:
    if story.hints.expected_text:
        return story.hints.expected_text
    text = build_story_query(story).lower()
    auth_variants = [
        ("sign in", "Sign in"),
        ("signin", "Sign in"),
        ("log in", "Login"),
        ("login", "Login"),
        ("sign up", "Sign up"),
        ("signup", "Sign up"),
        ("register", "Register"),
        ("dashboard", "Dashboard"),
        ("profile", "Profile"),
        ("home", "Home"),
    ]
    for needle, label in auth_variants:
        if needle in text:
            return label
    if story.acceptance_criteria:
        return story.acceptance_criteria[0].strip()[:120]
    title = re.sub(r"\b(user|should|can|be|able|to)\b", "", story.title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip(" -:")
    return title or None


def _infer_expected_selector(story: UserStoryRecord, route: str | None) -> str | None:
    if story.hints.expected_selector:
        return story.hints.expected_selector
    text = build_story_query(story).lower()
    route = (route or "").lower()
    if any(word in text for word in ("login", "sign in", "signin", "register", "sign up", "signup")) or any(
        word in route for word in ("login", "signin", "register", "signup")
    ):
        return "button[type='submit']"
    return None


def _infer_fallback_route(story: UserStoryRecord) -> str:
    if story.hints.path:
        return _normalize_route(story.hints.path)
    text = build_story_query(story).lower()
    if any(word in text for word in ("login", "log in", "sign in", "signin")):
        return "/login"
    if any(word in text for word in ("register", "sign up", "signup")):
        return "/register"
    if "dashboard" in text:
        return "/dashboard"
    if "profile" in text:
        return "/profile"
    return "/"


def build_frontend_story_plan(
    project: ProjectConfig,
    story: UserStoryRecord,
    workspace_path: str | Path | None = None,
) -> FrontendStoryTestPlan:
    discovery = discover_frontend_surface(project, workspace_path=workspace_path)
    fallback_route = _infer_fallback_route(story)
    expected_text = _infer_expected_text(story)
    expected_selector = _infer_expected_selector(story, fallback_route)
    if discovery.error_message:
        return FrontendStoryTestPlan(
            story_id=story.story_id,
            project_id=story.project_id,
            inferred_route=fallback_route,
            expected_text=expected_text,
            expected_selector=expected_selector,
            reasoning=(
                f"Frontend discovery unavailable: {discovery.error_message}. "
                f"Using story-based fallback route {fallback_route}."
            ),
        )

    scored_candidates = sorted(
        (
            FrontendRouteCandidate(
                route=item.route,
                source_path=item.source_path,
                route_type=item.route_type,
                score=round(item.score + _score_route_for_story(item.route, story), 2),
            )
            for item in discovery.routes
        ),
        key=lambda item: (-item.score, item.route),
    )
    inferred_route = story.hints.path or (scored_candidates[0].route if scored_candidates else fallback_route)
    expected_selector = _infer_expected_selector(story, inferred_route)
    reasoning = (
        f"Detected {discovery.framework or 'an unknown frontend'} with {len(discovery.routes)} candidate route(s). "
        f"Selected {inferred_route or '/'} as the best match for story '{story.title}'."
    )
    return FrontendStoryTestPlan(
        story_id=story.story_id,
        project_id=story.project_id,
        inferred_route=inferred_route,
        candidate_routes=scored_candidates[:5],
        expected_text=expected_text,
        expected_selector=expected_selector,
        reasoning=reasoning,
    )
