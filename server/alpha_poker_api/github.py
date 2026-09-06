from __future__ import annotations

import json
import urllib.error
import urllib.request
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException

from .config import Settings
from .db import Database, now_iso

# Build-time constant, matching .github/ISSUE_TEMPLATE/config.yml -- the only
# other place this repository identity appears in the codebase.
GITHUB_OWNER = "sethusehitch"
GITHUB_REPO = "alpha-poker"
GITHUB_API_BASE = "https://api.github.com"
CACHE_KEY = "contribute_summary"
CACHE_TTL = timedelta(minutes=10)
REQUEST_TIMEOUT_SECONDS = 8
# COMMUNITY_DESIGN_SPEC.md section 5.8 pins the "Good first issues" card to
# exactly this label -- "help wanted" issues still count in open_issue_count
# but are not promoted into the card.
HIGHLIGHT_LABELS = {"good first issue"}
_CACHE_REFRESH_LOCK = threading.Lock()


def repo_issue_url(number: int) -> str:
    return f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{number}"


def repo_pull_url(number: int) -> str:
    return f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/pull/{number}"


def _headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "alpha-poker-contribute-page",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def http_get_json(url: str, settings: Settings) -> Any:
    """Thin seam kept as a free function so tests can monkeypatch it."""
    request = urllib.request.Request(url, headers=_headers(settings))
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def http_post_json(url: str, body: dict[str, Any], settings: Settings) -> Any:
    payload = json.dumps(body).encode("utf-8")
    headers = {**_headers(settings), "Content-Type": "application/json"}
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _public_issue(item: dict[str, Any]) -> dict[str, Any]:
    labels = [label.get("name", "") for label in item.get("labels", []) if isinstance(label, dict)]
    assignee = item.get("assignee")
    return {
        "number": item["number"],
        "title": str(item.get("title") or "")[:200],
        "url": repo_issue_url(item["number"]),
        "labels": labels[:10],
        "assignee": assignee.get("login") if isinstance(assignee, dict) else None,
        "comments": int(item.get("comments") or 0),
    }


def fetch_github_summary(settings: Settings) -> dict[str, Any]:
    """Two core-REST-API calls (not the stricter-rate-limited Search API):
    one issues listing (used for both the open-issue count and the
    good-first-issue/help-wanted highlights) and one pull-request listing.
    """
    issues_url = (
        f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues"
        "?state=open&per_page=100&sort=created&direction=desc"
    )
    pulls_url = f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls?state=open&per_page=100"
    issues_response = http_get_json(issues_url, settings)
    pulls_response = http_get_json(pulls_url, settings)
    # GitHub's issues endpoint also returns pull requests; exclude them so
    # counts and highlighted rows are issues only.
    issues_only = [item for item in issues_response if "pull_request" not in item]
    highlighted = []
    for item in issues_only:
        names = {
            str(label.get("name", "")).strip().lower()
            for label in item.get("labels", [])
            if isinstance(label, dict)
        }
        if names & HIGHLIGHT_LABELS:
            highlighted.append(item)
        if len(highlighted) >= 5:
            break
    return {
        "good_first_issues": [_public_issue(item) for item in highlighted],
        "open_issue_count": len(issues_only),
        "open_pr_count": len(pulls_response),
        "fetched_at": now_iso(),
    }


def get_contribute_data(db: Database, settings: Settings) -> dict[str, Any]:
    cached = db.one("SELECT payload_json, fetched_at FROM github_cache WHERE cache_key=?", (CACHE_KEY,))
    if cached:
        fetched_at = datetime.fromisoformat(cached["fetched_at"].replace("Z", "+00:00"))
        if datetime.now(UTC) - fetched_at < CACHE_TTL:
            return {**json.loads(cached["payload_json"]), "stale": False}
    with _CACHE_REFRESH_LOCK:
        # Another request may have refreshed while this one waited.
        refreshed = db.one("SELECT payload_json, fetched_at FROM github_cache WHERE cache_key=?", (CACHE_KEY,))
        if refreshed:
            fetched_at = datetime.fromisoformat(refreshed["fetched_at"].replace("Z", "+00:00"))
            if datetime.now(UTC) - fetched_at < CACHE_TTL:
                return {**json.loads(refreshed["payload_json"]), "stale": False}
        try:
            summary = fetch_github_summary(settings)
        except Exception:
            fallback = refreshed or cached
            if fallback:
                return {**json.loads(fallback["payload_json"]), "stale": True}
            raise HTTPException(503, {"code": "api_unavailable", "message": "GitHub is unavailable"})
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO github_cache(cache_key,payload_json,fetched_at) VALUES(?,?,?) "
                "ON CONFLICT(cache_key) DO UPDATE SET payload_json=excluded.payload_json, "
                "fetched_at=excluded.fetched_at",
                (CACHE_KEY, json.dumps(summary), summary["fetched_at"]),
            )
        return {**summary, "stale": False}


def create_github_issue(settings: Settings, title: str, body: str) -> dict[str, Any]:
    if not settings.github_token:
        raise HTTPException(
            503, {"code": "github_not_configured", "message": "GitHub integration is not configured on this server"}
        )
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues"
    try:
        result = http_post_json(url, {"title": title, "body": body}, settings)
    except urllib.error.HTTPError as exc:
        raise HTTPException(502, {"code": "github_request_failed", "message": "GitHub rejected the request"}) from exc
    except Exception as exc:
        raise HTTPException(503, {"code": "api_unavailable", "message": "Could not reach GitHub"}) from exc
    return {"number": result["number"], "url": repo_issue_url(result["number"])}
