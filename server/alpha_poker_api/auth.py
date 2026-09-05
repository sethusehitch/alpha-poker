from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from .db import Database, now_iso


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{2,40}$")
SESSION_DAYS = 30
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError("Username must be 2 to 40 letters, numbers, underscores, or hyphens")
    return username


def validate_password(password: str) -> None:
    if not 8 <= len(password) <= 128:
        raise ValueError("Password must be 8 to 128 characters")


def hash_password(password: str, salt: bytes | None = None) -> str:
    validate_password(password)
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


DUMMY_PASSWORD_HASH = hash_password("alpha-poker-dummy-password", bytes(16))


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(digest_hex)),
        )
        return hmac.compare_digest(actual, bytes.fromhex(digest_hex))
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(db: Database, username: str) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(UTC) + timedelta(days=SESSION_DAYS)).isoformat().replace("+00:00", "Z")
    db.execute(
        "INSERT INTO auth_sessions(token_hash,username,created_at,expires_at,revoked_at) VALUES(?,?,?,?,NULL)",
        (token_digest(token), username, now_iso(), expires_at),
    )
    return token, expires_at


def authenticate_token(db: Database, authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    row = db.one(
        "SELECT username,expires_at,revoked_at FROM auth_sessions WHERE token_hash=?",
        (token_digest(token),),
    )
    if not row or row["revoked_at"] or row["expires_at"] <= now_iso():
        return None
    return row["username"]


def require_user(db: Database, authorization: str | None) -> str:
    username = authenticate_token(db, authorization)
    if not username:
        raise HTTPException(401, {"code": "authentication_required", "message": "Log in first"})
    return username


def revoke_session(db: Database, authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        return
    db.execute(
        "UPDATE auth_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
        (now_iso(), token_digest(authorization[7:].strip())),
    )
