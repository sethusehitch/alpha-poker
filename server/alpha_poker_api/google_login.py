"""Google identity, invite-gated onboarding, and first-party CLI approval.

OAuth credentials and pending tickets are never stored in browser localStorage.
Google email/name/photo are deliberately not used as public account identity.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sqlite3
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field

from .auth import issue_session, normalize_username, require_user, token_digest
from .db import now_iso


def expiry():
    return (datetime.now(UTC) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")


def fail(status, code, message):
    raise HTTPException(status, {"code": code, "message": message})


def exchange_identity(settings, code, verifier, nonce):
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2.id_token import verify_oauth2_token

    body = urllib.parse.urlencode({
        "code": code, "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code", "code_verifier": verifier,
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(
            "https://oauth2.googleapis.com/token", data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=15) as response:
            tokens = json.load(response)
        transport = GoogleRequest()
        def bounded_request(*args, **kwargs):
            kwargs.setdefault("timeout", 10)
            return transport(*args, **kwargs)
        claims = verify_oauth2_token(tokens["id_token"], bounded_request, settings.google_client_id)
        if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
            raise ValueError("issuer")
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise ValueError("nonce")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise ValueError("subject")
        return subject
    except Exception:
        # Never include Google response bodies, authorization codes, or tokens.
        fail(401, "google_failed", "Google sign-in could not be verified. Please try again.")


class Start(BaseModel):
    link: bool = False


class Callback(BaseModel):
    state: str = Field(min_length=20, max_length=256)
    code: str = Field(min_length=1, max_length=4096)


class Ticket(BaseModel):
    ticket: str = Field(min_length=20, max_length=256)


class Invite(Ticket):
    invite_code: str = Field(default="", max_length=128)


class Complete(Invite):
    username: str = Field(min_length=2, max_length=40)
    preset: str = "elephant"


class Device(BaseModel):
    device_code: str = Field(min_length=20, max_length=256)


class Approval(BaseModel):
    user_code: str = Field(min_length=9, max_length=9)


def register_google_routes(app, db, settings, limit):
    def enabled():
        return bool(settings.google_client_id and settings.google_client_secret)

    def cleanup():
        for table in ("google_flows", "google_signups", "browser_logins"):
            db.execute(f"DELETE FROM {table} WHERE expires_at<=?", (now_iso(),))

    def invite_ok(value):
        if settings.invite_code and not secrets.compare_digest(value.encode(), settings.invite_code.encode()):
            fail(403, "invite_invalid", "That invite code is not valid. Check with your league organizer.")

    def pending(ticket):
        row = db.one("SELECT * FROM google_signups WHERE ticket_hash=? AND expires_at>?", (token_digest(ticket), now_iso()))
        if not row:
            fail(401, "signup_expired", "Your sign-in expired. Please continue with Google again.")
        return row

    @app.get("/v1/auth/options")
    def options():
        return {"google_enabled": enabled(), "invite_required": bool(settings.invite_code)}

    @app.get("/v1/auth/google/connection")
    def connection(authorization: Annotated[str | None, Header()] = None):
        username = require_user(db, authorization)
        return {"connected": bool(db.one("SELECT 1 FROM google_identities WHERE username=?", (username,))), "enabled": enabled()}

    @app.post("/v1/auth/google/start")
    def start(body: Start, request: Request, authorization: Annotated[str | None, Header()] = None):
        limit(request, "google_start", 20, 300)
        if not enabled():
            fail(503, "google_unavailable", "Google sign-in is not configured yet. Use your username and password.")
        username = require_user(db, authorization) if body.link else None
        cleanup()
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        db.execute("INSERT INTO google_flows VALUES(?,?,?,?,?)", (token_digest(state), nonce, verifier, username, expiry()))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        query = urllib.parse.urlencode({"client_id": settings.google_client_id, "redirect_uri": settings.google_redirect_uri,
            "response_type": "code", "scope": "openid", "state": state, "nonce": nonce,
            "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account"})
        return {"url": "https://accounts.google.com/o/oauth2/v2/auth?" + query, "state": state}

    @app.post("/v1/auth/google/callback")
    def callback(body: Callback, request: Request):
        limit(request, "google_callback", 30, 300)
        if not enabled():
            fail(503, "google_unavailable", "Google sign-in is not configured.")
        with db.connect() as conn:
            row = conn.execute("DELETE FROM google_flows WHERE state_hash=? AND expires_at>? RETURNING *", (token_digest(body.state), now_iso())).fetchone()
        if not row:
            fail(401, "google_expired", "Your sign-in expired. Please try again.")
        subject = exchange_identity(settings, body.code, row["verifier"], row["nonce"])
        existing = db.one("SELECT username FROM google_identities WHERE subject=?", (subject,))
        if row["link_username"]:
            username = row["link_username"]
            if existing and existing["username"] != username:
                fail(409, "google_in_use", "That Google account is already connected to another player.")
            try:
                db.execute("INSERT INTO google_identities VALUES(?,?,?)", (subject, username, now_iso()))
            except sqlite3.IntegrityError:
                if not existing or existing["username"] != username:
                    fail(409, "already_connected", "Your account already has a Google login connected.")
            return {"linked": True}
        if existing:
            token, expires_at = issue_session(db, existing["username"])
            return {"username": existing["username"], "token": token, "expires_at": expires_at}
        ticket = secrets.token_urlsafe(32)
        db.execute("INSERT INTO google_signups VALUES(?,?,?)", (token_digest(ticket), subject, expiry()))
        return {"signup_required": True, "ticket": ticket}

    @app.post("/v1/auth/google/pending")
    def pending_status(body: Ticket):
        pending(body.ticket)
        return {"pending": True, "invite_required": bool(settings.invite_code)}

    @app.post("/v1/auth/google/invite")
    def check_invite(body: Invite, request: Request):
        limit(request, "google_invite", 8, 600)
        pending(body.ticket)
        invite_ok(body.invite_code)
        return {"valid": True}

    @app.post("/v1/auth/google/complete", status_code=201)
    def complete(body: Complete, request: Request):
        limit(request, "google_complete", 8, 600)
        invite_ok(body.invite_code)
        try:
            username = normalize_username(body.username)
        except ValueError as exc:
            fail(422, "username_invalid", str(exc))
        if username in settings.operator_usernames:
            fail(403, "username_reserved", "Choose a different username.")
        if body.preset not in {"elephant", "bear", "octopus", "bird"}:
            fail(422, "avatar_invalid", "Choose an available avatar.")
        try:
            with db.connect() as conn:
                row = conn.execute("DELETE FROM google_signups WHERE ticket_hash=? AND expires_at>? RETURNING subject", (token_digest(body.ticket), now_iso())).fetchone()
                if not row:
                    fail(401, "signup_expired", "Your sign-in expired. Please continue with Google again.")
                # Empty hash intentionally cannot authenticate with a password.
                conn.execute("INSERT INTO users VALUES(?,?,?,?)", (username, "", now_iso(), now_iso()))
                conn.execute("INSERT INTO google_identities VALUES(?,?,?)", (row["subject"], username, now_iso()))
                conn.execute("INSERT INTO account_avatars(username,preset,updated_at) VALUES(?,?,?)", (username, body.preset, now_iso()))
        except sqlite3.IntegrityError:
            fail(409, "account_conflict", "That username or Google account is already registered. Try another username or sign in again.")
        token, expires_at = issue_session(db, username)
        return {"username": username, "token": token, "expires_at": expires_at}

    @app.post("/v1/auth/browser/start")
    def device_start(request: Request):
        limit(request, "browser_start", 12, 600)
        cleanup()
        device = secrets.token_urlsafe(32)
        code = secrets.token_hex(4).upper()
        code = code[:4] + "-" + code[4:]
        db.execute("INSERT INTO browser_logins VALUES(?,?,NULL,?)", (token_digest(device), code, expiry()))
        return {"device_code": device, "user_code": code, "verification_uri": settings.public_web_url + "/authorize-cli", "expires_in": 600, "interval": 3}

    @app.post("/v1/auth/browser/approve")
    def approve(body: Approval, request: Request, authorization: Annotated[str | None, Header()] = None):
        limit(request, "browser_approve", 10, 600)
        username = require_user(db, authorization)
        with db.connect() as conn:
            row = conn.execute("UPDATE browser_logins SET username=? WHERE user_code=? AND username IS NULL AND expires_at>? RETURNING device_hash", (username, body.user_code.upper(), now_iso())).fetchone()
        if not row:
            fail(400, "code_invalid", "That code expired or was already approved. Start a new CLI login.")
        return {"approved": True}

    @app.post("/v1/auth/browser/poll")
    def poll(body: Device, request: Request):
        digest = token_digest(body.device_code)
        limit(request, "browser_poll:" + digest, 220, 600)
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM browser_logins WHERE device_hash=? AND expires_at>?", (digest, now_iso())).fetchone()
            if not row:
                fail(410, "login_expired", "Login expired. Run alpha-poker login --browser again.")
            if not row["username"]:
                return {"pending": True}
            claimed = conn.execute("DELETE FROM browser_logins WHERE device_hash=? RETURNING username", (digest,)).fetchone()
        if not claimed:
            fail(410, "login_expired", "This login was already used.")
        token, expires_at = issue_session(db, claimed["username"])
        return {"username": claimed["username"], "token": token, "expires_at": expires_at}
