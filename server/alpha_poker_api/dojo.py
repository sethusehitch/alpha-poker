"""Private account progress for explicitly self-reported local practice."""
import json
from typing import Literal
from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from alpha_poker.dojo import VERSION, IDS, catalog
from .auth import authenticate_token
from .db import now_iso


class LocalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str = Field(pattern=r"^dojo_[a-f0-9]{24}$")
    opponent: Literal["pebble", "anchor", "spark", "mirage", "summit"]
    opponent_version: str = Field(max_length=32)
    bot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    hands_played: int = Field(ge=2, le=400, multiple_of=2)
    net_chips: int = Field(ge=-800000, le=800000)
    bot_errors: int = Field(ge=0, le=400)
    seed: int = Field(ge=0, lt=2**31)

    @model_validator(mode="after")
    def bounds(self):
        if abs(self.net_chips) > self.hands_played * 2000 or self.bot_errors > self.hands_played:
            raise ValueError("Result exceeds the possible limits of this run")
        return self


def register_dojo_routes(app, db):
    def owner(authorization):
        username = authenticate_token(db, authorization)
        if not username:
            raise HTTPException(401, "Log in to sync or view private dojo progress")
        return username

    @app.get("/v1/dojo/opponents")
    def opponents():
        # Exact same latest-standing ordering as hosted training. Never return
        # submission paths, downloadable packages, tokens, or source code.
        leader = db.one("SELECT l.username,l.bot_name,l.elo_rating,l.submission_id FROM leaderboard l "
            "JOIN runs r ON r.id=l.run_id WHERE r.status='completed' AND r.official=1 "
            "ORDER BY r.completed_at DESC,r.requested_at DESC,l.rank LIMIT 1")
        available = None
        if leader:
            available = db.one("SELECT id FROM submissions WHERE id=?", (leader["submission_id"],))
            if not available:
                available = db.one("SELECT id FROM submissions WHERE username=? AND active=1 ORDER BY created_at DESC LIMIT 1", (leader["username"],))
        public_leader = {key: leader[key] for key in ("username", "bot_name", "elo_rating")} if leader and available else None
        return {**catalog(), "leader": public_leader}

    @app.get("/v1/dojo/progress")
    def progress(authorization: str | None = Header(None)):
        username = owner(authorization)
        rows = db.all("SELECT opponent,MAX(qualified) AS beaten,COUNT(*) AS runs FROM dojo_results "
            "WHERE username=? AND opponent_version=? GROUP BY opponent", (username, VERSION))
        saved = {row["opponent"]: {"beaten": bool(row["beaten"]), "runs": row["runs"]} for row in rows}
        return {"version": VERSION, "verification": "self_reported", "progress": {bot: saved.get(bot, {"beaten": False, "runs": 0}) for bot in IDS}}

    @app.post("/v1/dojo/results")
    def record(body: LocalResult, authorization: str | None = Header(None)):
        username = owner(authorization)
        if body.opponent_version != VERSION:
            raise HTTPException(409, "This dojo version is retired. Update the starter kit and run the current opponent.")
        payload = json.dumps(body.model_dump(), sort_keys=True)
        qualified = body.hands_played >= 200 and body.net_chips > 0 and body.bot_errors == 0
        with db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute("SELECT payload FROM dojo_results WHERE username=? AND run_id=?", (username, body.run_id)).fetchone()
            if previous and previous["payload"] != payload:
                raise HTTPException(409, "This run was already synced with different results")
            if not previous:
                total = conn.execute("SELECT COUNT(*) FROM dojo_results WHERE username=?", (username,)).fetchone()[0]
                if total >= 10000:
                    raise HTTPException(429, "Practice history limit reached. Local training and recaps remain available.")
                conn.execute("INSERT INTO dojo_results VALUES(?,?,?,?,?,?,?)", (username, body.run_id, body.opponent, VERSION, payload, int(qualified), now_iso()))
        return {"run_id": body.run_id, "opponent": body.opponent, "beaten": qualified, "verification": "self_reported", "public_elo_changed": False}
