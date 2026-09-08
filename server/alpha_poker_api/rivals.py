from __future__ import annotations

import hashlib
import asyncio
import json
import secrets
import sqlite3
from collections.abc import Callable
from typing import Annotated, Any, Literal
import threading

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .db import Database, now_iso


OPEN_STATUSES = ("pending", "queued", "running")
FINISHED_STATUSES = ("completed", "declined", "cancelled", "failed")


class ChallengeCreate(BaseModel):
    opponent_username: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")


def _latest_standing(db: Database, username: str) -> dict[str, Any] | None:
    return db.one(
        "SELECT l.* FROM leaderboard l JOIN runs r ON r.id=l.run_id "
        "WHERE l.username=? AND r.status='completed' AND r.official=1 "
        "ORDER BY r.completed_at DESC,r.requested_at DESC LIMIT 1",
        (username,),
    )


def _active_bot(db: Database, username: str) -> dict[str, Any] | None:
    return db.one(
        "SELECT id,bot_name,package_path FROM submissions WHERE username=? AND active=1 AND status='accepted' "
        "ORDER BY updated_at DESC LIMIT 1",
        (username,),
    )


def _participants(challenge: dict[str, Any]) -> tuple[str, str]:
    return challenge["challenger_username"], challenge["challenged_username"]


def _is_participant(challenge: dict[str, Any], username: str) -> bool:
    return username in _participants(challenge)


def _record(db: Database, player_a: str, player_b: str) -> dict[str, int]:
    rows = db.all(
        "SELECT winner_username FROM rival_challenges WHERE status='completed' "
        "AND ((challenger_username=? AND challenged_username=?) OR "
        "(challenger_username=? AND challenged_username=?))",
        (player_a, player_b, player_b, player_a),
    )
    a_wins = sum(row["winner_username"] == player_a for row in rows)
    b_wins = sum(row["winner_username"] == player_b for row in rows)
    return {
        "player_a_wins": a_wins,
        "player_b_wins": b_wins,
        "draws": len(rows) - a_wins - b_wins,
        "played": len(rows),
    }


def _nemesis(db: Database, username: str) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    opponents = db.all(
        "SELECT CASE WHEN challenger_username=? THEN challenged_username ELSE challenger_username END AS opponent,"
        "COUNT(*) AS played,"
        "SUM(CASE WHEN winner_username IS NOT NULL AND winner_username!=? THEN 1 ELSE 0 END) AS losses,"
        "MAX(completed_at) AS latest "
        "FROM rival_challenges WHERE status='completed' AND "
        "(challenger_username=? OR challenged_username=?) "
        "GROUP BY opponent HAVING COUNT(*)>=3",
        (username, username, username, username),
    )
    candidates.extend(opponents)
    if not candidates:
        return None
    winner = max(
        candidates,
        key=lambda row: (int(row["losses"] or 0), int(row["played"]), str(row["latest"] or "")),
    )
    # A rival who has never beaten the viewer is not meaningfully a nemesis.
    if int(winner["losses"] or 0) == 0:
        return None
    return winner


def _bot_names(db: Database, challenge: dict[str, Any]) -> dict[str, str | None]:
    result: dict[str, str | None] = {"challenger": None, "challenged": None}
    for key, submission_key in (
        ("challenger", "challenger_submission_id"),
        ("challenged", "challenged_submission_id"),
    ):
        if challenge.get(submission_key):
            row = db.one("SELECT bot_name FROM submissions WHERE id=?", (challenge[submission_key],))
            result[key] = row["bot_name"] if row else None
    if not result["challenger"]:
        bot = _active_bot(db, challenge["challenger_username"])
        result["challenger"] = bot["bot_name"] if bot else None
    if not result["challenged"]:
        bot = _active_bot(db, challenge["challenged_username"])
        result["challenged"] = bot["bot_name"] if bot else None
    return result


def public_challenge(db: Database, challenge: dict[str, Any], viewer: str | None = None) -> dict[str, Any]:
    opponent = None
    if viewer and _is_participant(challenge, viewer):
        opponent = (
            challenge["challenged_username"]
            if challenge["challenger_username"] == viewer
            else challenge["challenger_username"]
        )
    run_id = challenge.get("run_id")
    can_view_recap = viewer is None or _is_participant(challenge, viewer)
    winner = challenge.get("winner_username")
    viewer_result = None
    if viewer and challenge["status"] == "completed":
        viewer_result = "draw" if winner is None else "win" if viewer == winner else "loss"
    winner_first_score = None
    if winner:
        winner_score = int((
            challenge.get("series_score_a")
            if winner == challenge["challenger_username"]
            else challenge.get("series_score_b")
        ) or 0)
        loser_score = int((
            challenge.get("series_score_b")
            if winner == challenge["challenger_username"]
            else challenge.get("series_score_a")
        ) or 0)
        winner_first_score = [winner_score, loser_score]
    return {
        "challenge_id": challenge["id"],
        "challenger_username": challenge["challenger_username"],
        "challenged_username": challenge["challenged_username"],
        "opponent_username": opponent,
        "status": challenge["status"],
        "format": challenge.get("format") or "best_of_five_plhe",
        "best_of": 5,
        "series_score": {
            challenge["challenger_username"]: int(challenge.get("series_score_a") or 0),
            challenge["challenged_username"]: int(challenge.get("series_score_b") or 0),
        },
        "games_completed": int(challenge.get("games_completed") or 0),
        "hands_played": int(challenge.get("hands_played") or 0),
        "current_game": challenge.get("current_game"),
        "seed": challenge.get("seed"),
        "winner_username": winner,
        "viewer_result": viewer_result,
        "winner_first_score": winner_first_score,
        "run_id": run_id,
        "created_at": challenge["created_at"],
        "accepted_at": challenge.get("accepted_at"),
        "started_at": challenge.get("started_at"),
        "completed_at": challenge.get("completed_at"),
        "updated_at": challenge["updated_at"],
        "error": (
            "The match could not finish. Check the details, then try a new challenge."
            if challenge.get("error") else None
        ),
        "bot_names": _bot_names(db, challenge),
        "recap_url": f"/v1/challenges/{challenge['id']}/recap" if can_view_recap and challenge["status"] == "completed" else None,
        "artifacts_url": f"/v1/runs/{run_id}/artifacts" if can_view_recap and run_id and challenge["status"] == "completed" else None,
    }


def _history(
    db: Database,
    player_a: str,
    player_b: str,
    cursor: str | None,
    limit: int,
    viewer: str | None,
) -> dict[str, Any]:
    values: list[Any] = [player_a, player_b, player_b, player_a]
    cursor_sql = ""
    if cursor:
        cursor_row = db.one(
            "SELECT completed_at,id FROM rival_challenges WHERE id=? AND status='completed' AND "
            "((challenger_username=? AND challenged_username=?) OR (challenger_username=? AND challenged_username=?))",
            (cursor, player_a, player_b, player_b, player_a),
        )
        if not cursor_row:
            raise HTTPException(400, {"code": "cursor_invalid", "message": "History cursor is invalid"})
        cursor_sql = " AND (completed_at<? OR (completed_at=? AND id<?))"
        values.extend([cursor_row["completed_at"], cursor_row["completed_at"], cursor_row["id"]])
    values.append(limit + 1)
    rows = db.all(
        "SELECT * FROM rival_challenges WHERE status='completed' AND "
        "((challenger_username=? AND challenged_username=?) OR (challenger_username=? AND challenged_username=?))"
        + cursor_sql + " ORDER BY completed_at DESC,id DESC LIMIT ?",
        tuple(values),
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [public_challenge(db, row, viewer) for row in rows],
        "next_cursor": rows[-1]["id"] if has_more and rows else None,
    }


def _challenge_for_user(db: Database, challenge_id: str, username: str) -> dict[str, Any]:
    challenge = db.one("SELECT * FROM rival_challenges WHERE id=?", (challenge_id,))
    if not challenge:
        raise HTTPException(404, {"code": "challenge_not_found", "message": "Challenge not found"})
    if not _is_participant(challenge, username):
        raise HTTPException(403, {"code": "challenge_forbidden", "message": "Challenge belongs to other players"})
    return challenge


def _notification(conn, challenge: dict[str, Any], username: str, kind: str, bot_names: dict[str, Any]) -> None:
    opponent = (
        challenge["challenged_username"] if username == challenge["challenger_username"]
        else challenge["challenger_username"]
    )
    payload = {
        "challenge_id": challenge["id"],
        "opponent_username": opponent,
        "challenger_username": challenge["challenger_username"],
        "challenged_username": challenge["challenged_username"],
        "bot_names": bot_names,
        "status": challenge["status"],
    }
    conn.execute(
        "INSERT OR IGNORE INTO notifications(id,username,type,challenge_id,payload_json,created_at) VALUES(?,?,?,?,?,?)",
        (f"ntf_{challenge['id']}_{username}_{kind}", username, kind, challenge["id"], json.dumps(payload), now_iso()),
    )


def register_rival_routes(
    app: FastAPI,
    db: Database,
    resolve_user: Callable[[str | None, str | None], str],
    schedule_worker: Callable[[], None],
    package_lock: threading.Lock,
) -> None:
    def caller(authorization: str | None, local_username: str | None) -> str:
        return resolve_user(authorization, local_username)

    @app.get("/v1/rivals")
    def rivals_list(
        source: Literal["mine", "leaderboard", "suggested"] = "leaderboard",
        q: str = Query(default="", max_length=80),
        cursor: str | None = None,
        limit: int = Query(default=20, ge=1, le=50),
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
    ):
        username = caller(authorization, x_alpha_username)
        names: set[str]
        latest = db.one(
            "SELECT id FROM runs WHERE status='completed' AND official=1 "
            "ORDER BY completed_at DESC,requested_at DESC LIMIT 1"
        )
        standings = db.all("SELECT username FROM leaderboard WHERE run_id=?", (latest["id"],)) if latest else []
        candidate_names = {row["username"] for row in standings}
        candidate_names.update(row["username"] for row in db.all("SELECT DISTINCT username FROM submissions WHERE active=1"))
        if source == "mine":
            rows = db.all(
                "SELECT challenger_username,challenged_username,MAX(updated_at) AS last_activity_at "
                "FROM rival_challenges WHERE challenger_username=? OR challenged_username=? "
                "GROUP BY challenger_username,challenged_username ORDER BY last_activity_at DESC",
                (username, username),
            )
            activity = {}
            for row in rows:
                opponent = row["challenged_username"] if row["challenger_username"] == username else row["challenger_username"]
                activity[opponent] = max(activity.get(opponent, ""), row["last_activity_at"])
            names = set(activity)
        else:
            names = set(candidate_names)
            activity = {}
        names.discard(username)
        needle = q.strip().lower()
        entries = []
        nemesis = _nemesis(db, username)
        for name in names:
            bot = _active_bot(db, name)
            standing = _latest_standing(db, name)
            bot_name = bot["bot_name"] if bot else (standing["bot_name"] if standing else None)
            if needle and needle not in name.lower() and needle not in (bot_name or "").lower():
                continue
            record = _record(db, username, name)
            entries.append({
                "username": name,
                "bot_name": bot_name,
                "elo_rating": int(standing["elo_rating"]) if standing else 1200,
                "rank": int(standing["rank"]) if standing else None,
                "has_active_bot": bool(bot),
                "last_activity_at": activity.get(name),
                "direct_record": {
                    "wins": record["player_a_wins"], "losses": record["player_b_wins"],
                    "draws": record["draws"], "played": record["played"],
                },
                "is_nemesis": bool(nemesis and nemesis["opponent"] == name),
            })
        if source == "mine":
            entries.sort(key=lambda item: (str(item["last_activity_at"] or ""), item["username"]), reverse=True)
        elif source == "suggested":
            viewer_standing = _latest_standing(db, username)
            viewer_elo = int(viewer_standing["elo_rating"]) if viewer_standing else 1200
            entries.sort(
                key=lambda item: (
                    abs(int(item["elo_rating"]) - viewer_elo),
                    not bool(item["has_active_bot"]),
                    item["rank"] is None,
                    item["rank"] or 10**9,
                    item["username"],
                )
            )
        else:
            entries.sort(key=lambda item: (item["rank"] is None, item["rank"] or 10**9, item["username"]))
        offset = 0
        if cursor:
            try:
                offset = int(cursor)
            except ValueError as exc:
                raise HTTPException(400, {"code": "cursor_invalid", "message": "Rival cursor is invalid"}) from exc
        page = entries[offset:offset + limit]
        response = {
            "items": page,
            "next_cursor": str(offset + limit) if offset + limit < len(entries) else None,
            "viewer": {"has_active_bot": bool(_active_bot(db, username))},
        }
        if source == "mine" and not needle and not entries:
            viewer_standing = _latest_standing(db, username)
            viewer_elo = int(viewer_standing["elo_rating"]) if viewer_standing else 1200
            suggested = []
            for name in candidate_names - {username}:
                bot = _active_bot(db, name)
                standing = _latest_standing(db, name)
                record = _record(db, username, name)
                suggested.append({
                    "username": name,
                    "bot_name": bot["bot_name"] if bot else (standing["bot_name"] if standing else None),
                    "elo_rating": int(standing["elo_rating"]) if standing else 1200,
                    "rank": int(standing["rank"]) if standing else None,
                    "has_active_bot": bool(bot),
                    "last_activity_at": None,
                    "direct_record": {
                        "wins": record["player_a_wins"], "losses": record["player_b_wins"],
                        "draws": record["draws"], "played": record["played"],
                    },
                    "is_nemesis": False,
                })
            suggested.sort(
                key=lambda item: (
                    abs(int(item["elo_rating"]) - viewer_elo),
                    not bool(item["has_active_bot"]),
                    item["rank"] is None,
                    item["rank"] or 10**9,
                    item["username"],
                )
            )
            response["suggested_items"] = suggested[:3]
            response["suggested_for_elo"] = viewer_elo
        return response

    @app.get("/v1/rivals/{rival_username}")
    def rival_detail(
        rival_username: str,
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
    ):
        username = caller(authorization, x_alpha_username)
        if rival_username == username:
            raise HTTPException(400, {"code": "self_rival", "message": "Choose another player"})
        standing = _latest_standing(db, rival_username)
        # The prototype database includes a seeded public leaderboard before
        # those demo players have login accounts or uploaded packages. A rival
        # advertised by the leaderboard must still have a viewable profile;
        # challenge creation separately requires both players' active bots.
        if (
            not db.one("SELECT 1 FROM users WHERE username=?", (rival_username,))
            and not _active_bot(db, rival_username)
            and not standing
        ):
            raise HTTPException(404, {"code": "rival_not_found", "message": "Rival not found"})
        bot = _active_bot(db, rival_username)
        viewer_bot = _active_bot(db, username)
        record = _record(db, username, rival_username)
        nemesis = _nemesis(db, username)
        current = db.one(
            "SELECT * FROM rival_challenges WHERE status IN ('pending','queued','running') AND "
            "((challenger_username=? AND challenged_username=?) OR (challenger_username=? AND challenged_username=?)) "
            "ORDER BY created_at DESC LIMIT 1",
            (username, rival_username, rival_username, username),
        )
        history = _history(db, username, rival_username, None, 20, username)
        is_nemesis = bool(nemesis and nemesis["opponent"] == rival_username)
        return {
            "rival": {
                "username": rival_username,
                "bot_name": bot["bot_name"] if bot else (standing["bot_name"] if standing else None),
                "elo_rating": int(standing["elo_rating"]) if standing else 1200,
                "rank": int(standing["rank"]) if standing else None,
                "has_active_bot": bool(bot),
            },
            "viewer": {"username": username, "has_active_bot": bool(viewer_bot)},
            "direct_record": {
                "wins": record["player_a_wins"], "losses": record["player_b_wins"],
                "draws": record["draws"], "played": record["played"],
            },
            "is_nemesis": is_nemesis,
            "nemesis_explanation": (
                f"You have lost to {rival_username} {nemesis['losses']} times, more than any other rival."
                if is_nemesis else None
            ),
            "current_challenge": public_challenge(db, current, username) if current else None,
            "history": history,
        }

    @app.get("/v1/rivals/{rival_username}/history")
    def rival_history(
        rival_username: str,
        cursor: str | None = None,
        limit: int = Query(default=20, ge=1, le=50),
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
    ):
        username = caller(authorization, x_alpha_username)
        return {"player_a": username, "player_b": rival_username, **_history(db, username, rival_username, cursor, limit, username)}

    @app.get("/v1/rivalries/compare")
    def compare(
        player_a: str,
        player_b: str,
        cursor: str | None = None,
        limit: int = Query(default=20, ge=1, le=50),
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
    ):
        username = caller(authorization, x_alpha_username)
        if player_a == player_b:
            raise HTTPException(400, {"code": "players_invalid", "message": "Choose two different players"})
        return {
            "player_a": player_a,
            "player_b": player_b,
            "direct_record": _record(db, player_a, player_b),
            **_history(db, player_a, player_b, cursor, limit, username),
        }

    @app.post("/v1/challenges", status_code=201)
    async def challenge_create(
        body: ChallengeCreate,
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ):
        username = caller(authorization, x_alpha_username)
        opponent = body.opponent_username.lower()
        if opponent == username:
            raise HTTPException(400, {"code": "self_challenge", "message": "You cannot challenge yourself"})
        if idempotency_key and len(idempotency_key) > 200:
            raise HTTPException(400, {"code": "idempotency_key_invalid", "message": "Idempotency-Key is too long"})
        if idempotency_key:
            existing = db.one(
                "SELECT * FROM rival_challenges WHERE challenger_username=? AND idempotency_key=?",
                (username, idempotency_key),
            )
            if existing:
                return public_challenge(db, existing, username)
        challenger_bot = _active_bot(db, username)
        opponent_bot = _active_bot(db, opponent)
        if not challenger_bot:
            raise HTTPException(409, {"code": "active_bot_required", "message": "Submit an active bot before challenging a rival"})
        if not opponent_bot:
            raise HTTPException(409, {"code": "opponent_bot_required", "message": "That rival does not have an active bot"})
        open_challenge = db.one(
            "SELECT * FROM rival_challenges WHERE status IN ('pending','queued','running') AND "
            "((challenger_username=? AND challenged_username=?) OR (challenger_username=? AND challenged_username=?)) "
            "ORDER BY created_at DESC LIMIT 1",
            (username, opponent, opponent, username),
        )
        if open_challenge:
            return public_challenge(db, open_challenge, username)
        challenge_id = "ch_" + (
            hashlib.sha256(f"{username}\0{idempotency_key}".encode()).hexdigest()[:16]
            if idempotency_key else secrets.token_hex(8)
        )
        timestamp = now_iso()
        try:
            with db.connect() as conn:
                conn.execute(
                    "INSERT INTO rival_challenges(id,challenger_username,challenged_username,status,hand_count,seed,"
                    "idempotency_key,created_at,updated_at) VALUES(?,?,?,'pending',0,?,?,?,?)",
                    (challenge_id, username, opponent, secrets.randbelow(2**31), idempotency_key, timestamp, timestamp),
                )
                created = dict(conn.execute("SELECT * FROM rival_challenges WHERE id=?", (challenge_id,)).fetchone())
                _notification(conn, created, opponent, "challenge_received", {
                    "challenger": challenger_bot["bot_name"], "challenged": opponent_bot["bot_name"]
                })
        except sqlite3.IntegrityError:
            if idempotency_key:
                existing = db.one(
                    "SELECT * FROM rival_challenges WHERE challenger_username=? AND idempotency_key=?",
                    (username, idempotency_key),
                )
                if existing:
                    return public_challenge(db, existing, username)
            existing = db.one(
                "SELECT * FROM rival_challenges WHERE status IN ('pending','queued','running') AND "
                "((challenger_username=? AND challenged_username=?) OR (challenger_username=? AND challenged_username=?)) "
                "ORDER BY created_at DESC LIMIT 1",
                (username, opponent, opponent, username),
            )
            if existing:
                return public_challenge(db, existing, username)
            raise HTTPException(409, {"code": "challenge_conflict", "message": "A challenge is already open"})
        return public_challenge(db, db.one("SELECT * FROM rival_challenges WHERE id=?", (challenge_id,)), username)

    @app.get("/v1/challenges")
    def challenge_list(
        status: Literal["incoming", "running", "finished"] | None = None,
        cursor: str | None = None,
        limit: int = Query(default=20, ge=1, le=50),
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
    ):
        username = caller(authorization, x_alpha_username)
        clauses = ["(challenger_username=? OR challenged_username=?)"]
        values: list[Any] = [username, username]
        if status == "incoming":
            clauses.extend(["status='pending'", "challenged_username=?"])
            values.append(username)
        elif status == "running":
            clauses.append("status IN ('queued','running')")
        elif status == "finished":
            clauses.append("status IN ('completed','declined','cancelled','failed')")
        if cursor:
            cursor_row = db.one("SELECT updated_at,id FROM rival_challenges WHERE id=?", (cursor,))
            if not cursor_row:
                raise HTTPException(400, {"code": "cursor_invalid", "message": "Challenge cursor is invalid"})
            clauses.append("(updated_at<? OR (updated_at=? AND id<?))")
            values.extend([cursor_row["updated_at"], cursor_row["updated_at"], cursor_row["id"]])
        values.append(limit + 1)
        rows = db.all(
            "SELECT * FROM rival_challenges WHERE " + " AND ".join(clauses) + " ORDER BY updated_at DESC,id DESC LIMIT ?",
            tuple(values),
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {"items": [public_challenge(db, row, username) for row in rows], "next_cursor": rows[-1]["id"] if has_more and rows else None}

    @app.get("/v1/challenges/{challenge_id}")
    def challenge_get(
        challenge_id: str,
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
    ):
        username = caller(authorization, x_alpha_username)
        return public_challenge(db, _challenge_for_user(db, challenge_id, username), username)

    @app.post("/v1/challenges/{challenge_id}/accept")
    async def challenge_accept(
        challenge_id: str,
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ):
        username = caller(authorization, x_alpha_username)
        challenge = _challenge_for_user(db, challenge_id, username)
        if challenge["challenged_username"] != username:
            raise HTTPException(403, {"code": "transition_forbidden", "message": "Only the challenged player can accept"})
        if challenge["status"] in {"queued", "running", "completed"}:
            return public_challenge(db, challenge, username)
        if challenge["status"] != "pending":
            raise HTTPException(409, {"code": "transition_invalid", "message": f"Cannot accept a {challenge['status']} challenge"})
        # Share the package lifecycle lock with activation/pruning. Once the
        # queued state is committed, pruning recognizes both snapshots.
        def snapshot_and_queue() -> None:
            with package_lock:
                challenger_bot = _active_bot(db, challenge["challenger_username"])
                challenged_bot = _active_bot(db, challenge["challenged_username"])
                if not challenger_bot or not challenged_bot:
                    raise HTTPException(409, {"code": "active_bot_required", "message": "Both players need an active bot to accept"})
                timestamp = now_iso()
                with db.connect() as conn:
                    cursor = conn.execute(
                        "UPDATE rival_challenges SET status='queued',challenger_submission_id=?,challenged_submission_id=?,"
                        "accepted_at=?,updated_at=? WHERE id=? AND status='pending' AND challenged_username=?",
                        (challenger_bot["id"], challenged_bot["id"], timestamp, timestamp, challenge_id, username),
                    )
                    if cursor.rowcount != 1:
                        current = conn.execute("SELECT status FROM rival_challenges WHERE id=?", (challenge_id,)).fetchone()
                        if not current or current["status"] not in {"queued", "running", "completed"}:
                            raise HTTPException(409, {"code": "transition_conflict", "message": "Challenge changed before it could be accepted"})
        await asyncio.to_thread(snapshot_and_queue)
        schedule_worker()
        return public_challenge(db, db.one("SELECT * FROM rival_challenges WHERE id=?", (challenge_id,)), username)

    def terminal_transition(challenge_id: str, username: str, action: str) -> dict[str, Any]:
        challenge = _challenge_for_user(db, challenge_id, username)
        allowed = (
            challenge["challenged_username"] == username if action == "declined"
            else challenge["challenger_username"] == username
        )
        if not allowed:
            raise HTTPException(403, {"code": "transition_forbidden", "message": f"You cannot mark this challenge {action}"})
        if challenge["status"] == action:
            return challenge
        if challenge["status"] != "pending":
            verb = "decline" if action == "declined" else "cancel"
            raise HTTPException(409, {"code": "transition_invalid", "message": f"Cannot {verb} a {challenge['status']} challenge"})
        timestamp = now_iso()
        with db.connect() as conn:
            cursor = conn.execute(
                "UPDATE rival_challenges SET status=?,completed_at=?,updated_at=? WHERE id=? AND status='pending'",
                (action, timestamp, timestamp, challenge_id),
            )
            if cursor.rowcount != 1:
                raise HTTPException(409, {"code": "transition_conflict", "message": "Challenge changed before that action completed"})
        return db.one("SELECT * FROM rival_challenges WHERE id=?", (challenge_id,))

    @app.post("/v1/challenges/{challenge_id}/decline")
    def challenge_decline(
        challenge_id: str,
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ):
        username = caller(authorization, x_alpha_username)
        return public_challenge(db, terminal_transition(challenge_id, username, "declined"), username)

    @app.post("/v1/challenges/{challenge_id}/cancel")
    def challenge_cancel(
        challenge_id: str,
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ):
        username = caller(authorization, x_alpha_username)
        return public_challenge(db, terminal_transition(challenge_id, username, "cancelled"), username)

    @app.get("/v1/challenges/{challenge_id}/recap")
    def challenge_recap(
        challenge_id: str,
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
    ):
        username = caller(authorization, x_alpha_username)
        challenge = _challenge_for_user(db, challenge_id, username)
        if challenge["status"] != "completed" or not challenge["run_id"]:
            raise HTTPException(409, {"code": "recap_not_ready", "message": "Challenge recap is not ready"})
        matchup = db.one("SELECT * FROM matchups WHERE run_id=?", (challenge["run_id"],))
        hands = db.all(
            "SELECT id AS hand_id,hand_number,winner,pot FROM hands WHERE run_id=? ORDER BY pot DESC,hand_number LIMIT 10",
            (challenge["run_id"],),
        )
        from .jobs import summarize_run
        return {
            "challenge": public_challenge(db, challenge, username),
            "matchup": matchup,
            "summary": summarize_run(db, challenge["run_id"]),
            "best_hands": hands,
            "artifacts_url": f"/v1/runs/{challenge['run_id']}/artifacts",
        }

    @app.get("/v1/notifications")
    def notification_list(
        cursor: str | None = None,
        limit: int = Query(default=20, ge=1, le=50),
        unread: bool = False,
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
    ):
        username = caller(authorization, x_alpha_username)
        clauses = ["username=?"]
        values: list[Any] = [username]
        if unread:
            clauses.append("read_at IS NULL")
        if cursor:
            cursor_row = db.one("SELECT created_at,id,username FROM notifications WHERE id=?", (cursor,))
            if not cursor_row or cursor_row["username"] != username:
                raise HTTPException(400, {"code": "cursor_invalid", "message": "Notification cursor is invalid"})
            clauses.append("(created_at<? OR (created_at=? AND id<?))")
            values.extend([cursor_row["created_at"], cursor_row["created_at"], cursor_row["id"]])
        values.append(limit + 1)
        rows = db.all(
            "SELECT * FROM notifications WHERE " + " AND ".join(clauses) + " ORDER BY created_at DESC,id DESC LIMIT ?",
            tuple(values),
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        unread_count = int(db.one("SELECT COUNT(*) AS n FROM notifications WHERE username=? AND read_at IS NULL", (username,))["n"])
        return {
            "items": [{
                "notification_id": row["id"], "type": row["type"], "challenge_id": row["challenge_id"],
                "payload": json.loads(row["payload_json"]), "created_at": row["created_at"], "read_at": row["read_at"],
            } for row in rows],
            "unread_count": unread_count,
            "next_cursor": rows[-1]["id"] if has_more and rows else None,
        }

    @app.post("/v1/notifications/{notification_id}/read")
    def notification_read(
        notification_id: str,
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
    ):
        username = caller(authorization, x_alpha_username)
        row = db.one("SELECT * FROM notifications WHERE id=?", (notification_id,))
        if not row:
            raise HTTPException(404, {"code": "notification_not_found", "message": "Notification not found"})
        if row["username"] != username:
            raise HTTPException(403, {"code": "notification_forbidden", "message": "Notification belongs to another account"})
        db.execute("UPDATE notifications SET read_at=COALESCE(read_at,?) WHERE id=?", (now_iso(), notification_id))
        row = db.one("SELECT * FROM notifications WHERE id=?", (notification_id,))
        return {
            "notification_id": row["id"], "type": row["type"], "challenge_id": row["challenge_id"],
            "payload": json.loads(row["payload_json"]), "created_at": row["created_at"], "read_at": row["read_at"],
        }

    @app.post("/v1/notifications/read-all")
    def notifications_read_all(
        authorization: str | None = Header(None),
        x_alpha_username: str | None = Header(None),
    ):
        username = caller(authorization, x_alpha_username)
        with db.connect() as conn:
            cursor = conn.execute(
                "UPDATE notifications SET read_at=? WHERE username=? AND read_at IS NULL",
                (now_iso(), username),
            )
            return {"read_count": cursor.rowcount}
