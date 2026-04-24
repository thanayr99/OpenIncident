from __future__ import annotations

import os
from time import perf_counter
from typing import Any

import requests

from models import ProjectBrowserCheckRequest


def run_http_browser_check(target_url: str, request: ProjectBrowserCheckRequest) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        response = requests.get(target_url, timeout=request.timeout_seconds)
    except requests.RequestException as exc:
        return {
            "status": "unreachable",
            "status_code": None,
            "response_time_ms": round((perf_counter() - started_at) * 1000, 2),
            "error_message": f"HTTP browser check could not reach the target: {exc}",
            "response_excerpt": None,
            "engine": "http",
            "observed_url": target_url,
            "page_title": None,
        }

    response_time_ms = round((perf_counter() - started_at) * 1000, 2)

    error_message = None
    if request.expected_text is not None and request.expected_text not in response.text:
        error_message = f"Expected page text not found: {request.expected_text}"
    is_healthy = response.status_code == 200 and error_message is None

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "status_code": response.status_code,
        "response_time_ms": response_time_ms,
        "error_message": error_message if error_message else (None if response.status_code == 200 else f"Expected 200, got {response.status_code}"),
        "response_excerpt": response.text[:300] if response.text else None,
        "engine": "http",
        "observed_url": target_url,
        "page_title": None,
    }


def run_playwright_browser_check(target_url: str, request: ProjectBrowserCheckRequest) -> dict[str, Any]:
    if os.getenv("OPENINCIDENT_DISABLE_PLAYWRIGHT", "").lower() in {"1", "true", "yes"}:
        return {
            "status": "tooling_error",
            "status_code": None,
            "response_time_ms": None,
            "error_message": "Playwright is disabled by OPENINCIDENT_DISABLE_PLAYWRIGHT, using fallback validation.",
            "response_excerpt": None,
            "engine": "playwright",
            "observed_url": target_url,
            "page_title": None,
        }

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "status": "tooling_error",
            "status_code": None,
            "response_time_ms": None,
            "error_message": "Playwright is not installed. Run `pip install playwright` and `python -m playwright install chromium`.",
            "response_excerpt": None,
            "engine": "playwright",
            "observed_url": target_url,
            "page_title": None,
        }

    started_at = perf_counter()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                response = page.goto(target_url, wait_until=request.wait_until, timeout=int(request.timeout_seconds * 1000))
                page.wait_for_load_state("networkidle", timeout=int(request.timeout_seconds * 1000))
                page_title = page.title()
                visible_text = page.locator("body").inner_text(timeout=int(request.timeout_seconds * 1000))
                observed_url = page.url
                response_time_ms = round((perf_counter() - started_at) * 1000, 2)
                status_code = response.status if response is not None else None

                error_message = None
                if request.expected_selector:
                    try:
                        page.locator(request.expected_selector).first.wait_for(
                            state="visible",
                            timeout=int(request.timeout_seconds * 1000),
                        )
                    except PlaywrightTimeoutError:
                        error_message = f"Expected selector not found: {request.expected_selector}"
                if error_message is None and request.expected_text:
                    if request.expected_text not in visible_text:
                        error_message = f"Expected visible text not found: {request.expected_text}"

                is_healthy = (status_code == 200 or status_code is None) and error_message is None
                return {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "status_code": status_code,
                    "response_time_ms": response_time_ms,
                    "error_message": error_message,
                    "response_excerpt": visible_text[:300] if visible_text else None,
                    "engine": "playwright",
                    "observed_url": observed_url,
                    "page_title": page_title,
                }
            except PlaywrightTimeoutError:
                return {
                    "status": "unreachable",
                    "status_code": None,
                    "response_time_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_message": f"Playwright timed out after {request.timeout_seconds} seconds.",
                    "response_excerpt": None,
                    "engine": "playwright",
                    "observed_url": page.url or target_url,
                    "page_title": None,
                }
            finally:
                browser.close()
    except Exception as exc:
        return {
            "status": "tooling_error",
            "status_code": None,
            "response_time_ms": round((perf_counter() - started_at) * 1000, 2),
            "error_message": f"Playwright launch failed: {exc}",
            "response_excerpt": None,
            "engine": "playwright",
            "observed_url": target_url,
            "page_title": None,
        }
