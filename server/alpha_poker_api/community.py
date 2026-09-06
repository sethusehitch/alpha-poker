from __future__ import annotations

import secrets
import ipaddress
import threading
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from .auth import authenticate_token, require_user
from .config import Settings
from .db import Database, now_iso
from .github import create_github_issue, get_contribute_data
from .models import (
    FeatureRequestCreate,
    FeatureRequestHide,
    FeatureRequestStatusUpdate,
    FeatureRequestVote,
    FeedbackCreate,
)
from .ratelimit import RateLimiter
from .sanitize import clean_text

FEATURE_STATUSES = ("submitted", "under_review", "planned", "in_progress", "shipped", "declined")
PAGE_SIZE = 25
TITLE_MIN_LENGTH = 4
TITLE_MAX_LENGTH = 80
DETAILS_MAX_LENGTH = 500
FEEDBACK_MESSAGE_MIN_LENGTH = 3
FEEDBACK_MESSAGE_MAX_LENGTH = 500

TITLE_VALIDATION_ERROR = {
    "code": "validation_error",
    "message": "That title didn't work. Keep it under 80 characters and try again.",
}
DETAILS_VALIDATION_ERROR = {
    "code": "validation_error",
    "message": "Details must be 500 characters or fewer.",
}
FEEDBACK_VALIDATION_ERROR = {
    "code": "validation_error",
    "message": "That message is too long. Keep it under 500 characters.",
}
FEATURE_RATE_LIMITED = {
    "code": "rate_limited",
    "message": "You're posting quickly. Try again in a minute.",
}
FEEDBACK_RATE_LIMITED = {
    "code": "rate_limited",
    "message": "You're sending a lot right now. Try again in a minute.",
}
REQUEST_NOT_FOUND = {"code": "request_not_found", "message": "Feature request not found"}
OPERATOR_REQUIRED = {"code": "operator_required", "message": "Operator access required"}


def is_operator_username(settings: Settings, username: str | None) -> bool:
    """Mirrors require_operator's gate for read-only `is_operator` flags.

    When auth is not required (solo local dev), every session is treated as
    the operator so local development can exercise the moderation UI.
    """
    if not settings.auth_required:
        return True
    return bool(username) and username in settings.operator_usernames


def register_community_routes(app: FastAPI, db: Database, settings: Settings) -> None:
    limiter = RateLimiter()
    promotion_lock = threading.Lock()

    def client_key(request: Request, username: str | None) -> str:
        if username:
            return f"user:{username}"
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        client = request.client
        if forwarded:
            try:
                forwarded = str(ipaddress.ip_address(forwarded))
            except ValueError:
                forwarded = ""
        return f"ip:{forwarded or (client.host if client else 'unknown')}"

    def enforce_rate_limit(
        request: Request, username: str | None, scope: str, limit: int, window_seconds: float, detail: dict[str, str]
    ) -> None:
        key = f"{scope}:{client_key(request, username)}"
        if not limiter.allow(key, limit, window_seconds):
            raise HTTPException(429, detail)

    def optional_username(authorization: str | None) -> str | None:
        return authenticate_token(db, authorization)

    def required_username(authorization: str | None) -> str:
        if settings.auth_required:
            return require_user(db, authorization)
        return authenticate_token(db, authorization) or "local"

    def feedback_client_context(request: Request) -> str:
        """Keep only coarse, non-identifying browser/device categories."""
        user_agent = request.headers.get("user-agent", "").lower()
        if "edg/" in user_agent:
            browser = "Edge"
        elif "firefox/" in user_agent:
            browser = "Firefox"
        elif "chrome/" in user_agent or "crios/" in user_agent:
            browser = "Chrome"
        elif "safari/" in user_agent:
            browser = "Safari"
        else:
            browser = "Other"
        device = "mobile" if any(marker in user_agent for marker in ("mobile", "android", "iphone", "ipad")) else "desktop"
        return f"{browser}/{device}"

    def require_operator(authorization: str | None) -> None:
        # Mirrors /v1/admin/runs: when auth is not required (solo local dev),
        # operator gating is a no-op, matching that existing precedent.
        if not settings.auth_required:
            return
        username = require_user(db, authorization)
        if not is_operator_username(settings, username):
            raise HTTPException(403, OPERATOR_REQUIRED)

    def public_feature_request(row: dict[str, Any]) -> dict[str, Any]:
        vote_value = row.get("my_vote_value")
        my_vote = "up" if vote_value == 1 else "down" if vote_value == -1 else None
        status = row["status"] if row["status"] in FEATURE_STATUSES else "submitted"
        return {
            "id": row["id"],
            "title": row["title"],
            "details": row["details"],
            "status": status,
            "score": int(row["score"] or 0),
            "my_vote": my_vote,
            "author": row["author_username"],
            "created_at": row["created_at"],
            "github_issue_url": row["github_issue_url"],
        }

    def fetch_public_feature_request(request_id: str, viewer: str | None) -> dict[str, Any] | None:
        row = db.one(
            "SELECT fr.*, "
            "COALESCE((SELECT SUM(value) FROM feature_votes WHERE request_id=fr.id),0) AS score, "
            "(SELECT value FROM feature_votes WHERE request_id=fr.id AND username=?) AS my_vote_value "
            "FROM feature_requests fr WHERE fr.id=?",
            (viewer, request_id),
        )
        return public_feature_request(row) if row else None

    @app.get("/v1/feature-requests")
    def list_feature_requests(
        tab: str = "top", cursor: str | None = None, authorization: str | None = Header(None)
    ):
        viewer = optional_username(authorization)
        offset = 0
        if cursor:
            try:
                offset = max(0, int(cursor))
            except ValueError:
                offset = 0
        where = "WHERE fr.hidden = 0"
        if tab == "planned":
            where += " AND fr.status IN ('planned','in_progress','shipped')"
        if tab == "new":
            order = "fr.created_at DESC"
        elif tab == "planned":
            order = (
                "CASE fr.status WHEN 'planned' THEN 0 WHEN 'in_progress' THEN 1 WHEN 'shipped' THEN 2 ELSE 3 END, "
                "score DESC, fr.created_at DESC"
            )
        else:
            order = "score DESC, fr.created_at DESC"
        query = (
            "SELECT fr.*, "
            "COALESCE((SELECT SUM(value) FROM feature_votes WHERE request_id=fr.id),0) AS score, "
            "(SELECT value FROM feature_votes WHERE request_id=fr.id AND username=?) AS my_vote_value "
            f"FROM feature_requests fr {where} ORDER BY {order} LIMIT ? OFFSET ?"
        )
        rows = db.all(query, (viewer, PAGE_SIZE + 1, offset))
        has_more = len(rows) > PAGE_SIZE
        items = [public_feature_request(row) for row in rows[:PAGE_SIZE]]
        next_cursor = str(offset + PAGE_SIZE) if has_more else None
        return {"items": items, "next_cursor": next_cursor}

    @app.post("/v1/feature-requests", status_code=201)
    def create_feature_request(
        body: FeatureRequestCreate, request: Request, authorization: str | None = Header(None)
    ):
        username = required_username(authorization)
        enforce_rate_limit(request, username, "feature_create", 5, 600, FEATURE_RATE_LIMITED)
        try:
            title = clean_text(body.title)
        except ValueError:
            raise HTTPException(400, TITLE_VALIDATION_ERROR)
        if len(title) < TITLE_MIN_LENGTH or len(title) > TITLE_MAX_LENGTH:
            raise HTTPException(400, TITLE_VALIDATION_ERROR)
        details: str | None = None
        if body.details and body.details.strip():
            try:
                details = clean_text(body.details)
            except ValueError:
                raise HTTPException(400, DETAILS_VALIDATION_ERROR)
            if len(details) > DETAILS_MAX_LENGTH:
                raise HTTPException(400, DETAILS_VALIDATION_ERROR)
        duplicate = db.one(
            "SELECT id FROM feature_requests WHERE hidden=0 AND lower(title)=lower(?)", (title,)
        )
        if duplicate:
            raise HTTPException(409, {"code": "duplicate_request", "message": "Someone already suggested that. Look for it in the list."})
        request_id = "feat_" + secrets.token_hex(8)
        timestamp = now_iso()
        db.execute(
            "INSERT INTO feature_requests(id,title,details,status,author_username,hidden,created_at,updated_at) "
            "VALUES(?,?,?,'submitted',?,0,?,?)",
            (request_id, title, details, username, timestamp, timestamp),
        )
        return fetch_public_feature_request(request_id, username)

    @app.post("/v1/feature-requests/{request_id}/vote")
    def vote_feature_request(
        request_id: str, body: FeatureRequestVote, request: Request, authorization: str | None = Header(None)
    ):
        username = required_username(authorization)
        enforce_rate_limit(request, username, "feature_vote", 60, 60, FEATURE_RATE_LIMITED)
        with db.connect() as conn:
            exists = conn.execute("SELECT 1 FROM feature_requests WHERE id=? AND hidden=0", (request_id,)).fetchone()
            if not exists:
                raise HTTPException(404, REQUEST_NOT_FOUND)
            if body.value == 0:
                conn.execute("DELETE FROM feature_votes WHERE request_id=? AND username=?", (request_id, username))
            else:
                timestamp = now_iso()
                conn.execute(
                    "INSERT INTO feature_votes(request_id,username,value,created_at,updated_at) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(request_id,username) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                    (request_id, username, body.value, timestamp, timestamp),
                )
            score = conn.execute(
                "SELECT COALESCE(SUM(value),0) AS score FROM feature_votes WHERE request_id=?", (request_id,)
            ).fetchone()["score"]
        my_vote = {1: "up", -1: "down", 0: None}[body.value]
        return {"score": int(score), "my_vote": my_vote}

    @app.patch("/v1/feature-requests/{request_id}")
    def update_feature_request_status(
        request_id: str, body: FeatureRequestStatusUpdate, authorization: str | None = Header(None)
    ):
        require_operator(authorization)
        if not db.one("SELECT 1 FROM feature_requests WHERE id=?", (request_id,)):
            raise HTTPException(404, REQUEST_NOT_FOUND)
        db.execute(
            "UPDATE feature_requests SET status=?, updated_at=? WHERE id=?", (body.status, now_iso(), request_id)
        )
        return fetch_public_feature_request(request_id, None)

    @app.post("/v1/feature-requests/{request_id}/hide", status_code=204)
    def hide_feature_request(
        request_id: str, body: FeatureRequestHide, authorization: str | None = Header(None)
    ):
        require_operator(authorization)
        if not db.one("SELECT 1 FROM feature_requests WHERE id=?", (request_id,)):
            raise HTTPException(404, REQUEST_NOT_FOUND)
        db.execute(
            "UPDATE feature_requests SET hidden=?, updated_at=? WHERE id=?",
            (1 if body.hidden else 0, now_iso(), request_id),
        )
        return None

    @app.post("/v1/feature-requests/{request_id}/promote")
    def promote_feature_request(
        request_id: str,
        authorization: str | None = Header(None),
        x_alpha_operator: str | None = Header(None),
    ):
        # Deliberately mirrors /v1/admin/runs's operator-token gate exactly --
        # this is an operator-API-only action with no browser affordance, so
        # the shared operator secret never needs to reach client JavaScript.
        if settings.auth_required:
            username = require_user(db, authorization)
            if not is_operator_username(settings, username):
                raise HTTPException(403, OPERATOR_REQUIRED)
            if not settings.operator_token or not x_alpha_operator or not secrets.compare_digest(
                x_alpha_operator, settings.operator_token
            ):
                raise HTTPException(403, OPERATOR_REQUIRED)
        # One deployment has one API process. Serializing this short operator
        # action makes the read/create/write sequence idempotent even when a
        # client retries before the first GitHub request returns.
        with promotion_lock:
            row = db.one("SELECT * FROM feature_requests WHERE id=?", (request_id,))
            if not row:
                raise HTTPException(404, REQUEST_NOT_FOUND)
            if row["github_issue_number"]:
                return {
                    "issue_number": row["github_issue_number"],
                    "issue_url": row["github_issue_url"],
                    "already_promoted": True,
                }
            if row.get("github_promotion_state") in {"creating", "needs_reconciliation"}:
                raise HTTPException(
                    409,
                    {"code": "promotion_needs_reconciliation", "message": "Check GitHub before retrying this promotion"},
                )
            db.execute(
                "UPDATE feature_requests SET github_promotion_state='creating', updated_at=? WHERE id=?",
                (now_iso(), request_id),
            )
            try:
                issue = create_github_issue(settings, title=row["title"], body=row["details"] or "")
            except Exception:
                # The upstream request may have succeeded before its response
                # was lost. Fail closed so a retry cannot create a duplicate.
                db.execute(
                    "UPDATE feature_requests SET github_promotion_state='needs_reconciliation', updated_at=? WHERE id=?",
                    (now_iso(), request_id),
                )
                raise
            db.execute(
                "UPDATE feature_requests SET github_issue_number=?, github_issue_url=?, github_promotion_state='promoted', updated_at=? WHERE id=?",
                (issue["number"], issue["url"], now_iso(), request_id),
            )
            return {"issue_number": issue["number"], "issue_url": issue["url"], "already_promoted": False}

    @app.post("/v1/feedback", status_code=204)
    def submit_feedback(body: FeedbackCreate, request: Request, authorization: str | None = Header(None)):
        username = optional_username(authorization)
        enforce_rate_limit(request, username, "feedback", 5, 600, FEEDBACK_RATE_LIMITED)
        try:
            message = clean_text(body.message)
        except ValueError:
            raise HTTPException(400, FEEDBACK_VALIDATION_ERROR)
        if len(message) < FEEDBACK_MESSAGE_MIN_LENGTH or len(message) > FEEDBACK_MESSAGE_MAX_LENGTH:
            raise HTTPException(400, FEEDBACK_VALIDATION_ERROR)
        try:
            path = clean_text(body.path).split("?", 1)[0].split("#", 1)[0][:200]
        except ValueError:
            path = "/"
        if not path.startswith("/"):
            path = "/"
        client_context = feedback_client_context(request)
        db.execute(
            "INSERT INTO feedback(id,username,type,message,path,client_context,created_at) VALUES(?,?,?,?,?,?,?)",
            ("fb_" + secrets.token_hex(8), username, body.type, message, path, client_context, now_iso()),
        )
        return None

    @app.get("/v1/github/issues")
    def github_issues():
        return get_contribute_data(db, settings)
