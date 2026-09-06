from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from .db import Database, now_iso


def create_session(db: Database, username: str, hand_limit: int, schema_version: str) -> dict[str, Any]:
    leader = db.one(
        "SELECT l.username, l.submission_id FROM leaderboard l JOIN runs r ON r.id=l.run_id "
        "WHERE r.status='completed' AND r.official=1 "
        "ORDER BY r.completed_at DESC, r.requested_at DESC, l.rank LIMIT 1"
    )
    leader_username = leader["username"] if leader else "house-bot"
    leader_submission = None
    if leader and leader.get("submission_id"):
        leader_submission = db.one("SELECT id FROM submissions WHERE id=?", (leader["submission_id"],))
    if leader_submission is None:
        leader_submission = db.one(
            "SELECT id FROM submissions WHERE username=? AND active=1 ORDER BY created_at DESC LIMIT 1",
            (leader_username,),
        )
    session_id = "trn_" + secrets.token_hex(8)
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    db.execute(
        "INSERT INTO training_sessions(id,username,opponent,leader_username,leader_submission_id,hand_limit,status,token,schema_version,created_at,expires_at) VALUES(?,?,?,?,?,?,'ready',?,?,?,?)",
        (session_id, username, "leader", leader_username, leader_submission["id"] if leader_submission else None, hand_limit, token, schema_version, now_iso(), expires_at),
    )
    return {"session_id": session_id, "training_token": token, "expires_at": expires_at}


def emit(db: Database, session_id: str, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute("SELECT seq FROM training_sessions WHERE id=?", (session_id,)).fetchone()
        seq = int(row["seq"]) + 1
        event = {"type": event_type, "seq": seq, "session_id": session_id, "payload": payload or {}}
        conn.execute("UPDATE training_sessions SET seq=? WHERE id=?", (seq, session_id))
        conn.execute("INSERT INTO training_events VALUES(?,?,?)", (session_id, seq, json.dumps(event)))
    return event


def action_request(db: Database, session_id: str, state: dict[str, Any]) -> dict[str, Any]:
    session = db.one("SELECT * FROM training_sessions WHERE id=?", (session_id,))
    hand_number = int(session["hands_played"]) + 1
    return emit(db, session_id, "action.requested", {
        "hand_id": f"{session_id}_hand_{hand_number}",
        "turn_id": f"{session_id}_turn_{hand_number}_{secrets.token_hex(4)}",
        "turn_token": secrets.token_urlsafe(16),
        "deadline_ms": 250,
        "state": state,
    })


def remembered_action(db: Database, session_id: str, action_id: str) -> dict[str, Any] | None:
    row = db.one("SELECT response FROM training_actions WHERE session_id=? AND client_action_id=?", (session_id, action_id))
    return json.loads(row["response"]) if row else None


def remember_action(db: Database, session_id: str, action_id: str, response: dict[str, Any]) -> None:
    db.execute("INSERT OR IGNORE INTO training_actions VALUES(?,?,?)", (session_id, action_id, json.dumps(response)))
