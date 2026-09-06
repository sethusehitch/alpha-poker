from __future__ import annotations

import asyncio
import hashlib
import io
import ipaddress
import json
import logging
import re
import secrets
import threading
import zipfile
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse

from .auth import DUMMY_PASSWORD_HASH, authenticate_token, hash_password, issue_session, normalize_username, require_user, revoke_session, verify_password
from .community import is_operator_username, register_community_routes
from .config import Settings
from .db import Database, now_iso
from .jobs import archive_and_prune, archive_run, build_run_artifact, prune_submission_packages, run_official_league, summarize_run, validate_submission
from .models import LoginRequest, RegisterRequest, RunCreate, TrainingCreate
from .ratelimit import RateLimiter
from .training import action_request, create_session, emit, remember_action, remembered_action
from .training_runtime import advance_leader, build_runtime, persist_completed_hand, public_action_to_engine, start_hand

MAX_ZIP_BYTES = 2 * 1024 * 1024
CAPABILITY_TOKEN_PATTERN = re.compile(r"([?&]token=)[^&\s\"]+")


class RedactCapabilityTokens(logging.Filter):
    """Prevent short-lived WebSocket capabilities from entering Uvicorn logs."""

    @staticmethod
    def redact(value: Any) -> Any:
        if isinstance(value, str):
            return CAPABILITY_TOKEN_PATTERN.sub(r"\1[redacted]", value)
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(self.redact(value) for value in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: self.redact(value) for key, value in record.args.items()}
        return True


def public_submission(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "submission_id": row["id"], "username": row["username"], "bot_name": row["bot_name"],
        "filename": row["original_filename"], "sha256": row["sha256"], "status": row["status"],
        "active": bool(row["active"]), "error": row["error"], "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_dirs()
    db = Database(settings.database_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        for logger_name in ("uvicorn.error", "uvicorn.access"):
            logger = logging.getLogger(logger_name)
            if not any(isinstance(item, RedactCapabilityTokens) for item in logger.filters):
                logger.addFilter(RedactCapabilityTokens())
        db.initialize(settings.seed_demo_data)
        db.execute("DELETE FROM auth_sessions WHERE expires_at<=?", (now_iso(),))
        feedback_cutoff = (datetime.now(UTC) - timedelta(days=settings.feedback_retention_days)).isoformat().replace("+00:00", "Z")
        db.execute("DELETE FROM feedback WHERE created_at<?", (feedback_cutoff,))
        prune_submission_packages(db)
        if settings.auto_run_on_accept:
            queue = db.one("SELECT * FROM league_queue WHERE singleton=1")
            if queue and queue["requested_generation"] > queue["completed_generation"]:
                app.state.auto_run_task = asyncio.create_task(auto_run_worker())
        try:
            yield
        finally:
            for runtime in list(app.state.training_runtimes.values()):
                runtime.close()
            app.state.training_runtimes.clear()
            task = app.state.auto_run_task
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(title="Alpha Poker API", version="0.1.0", lifespan=lifespan)
    app.state.db = db
    app.state.settings = settings
    app.state.training_runtimes = {}
    app.state.auto_run_requested = False
    app.state.auto_run_task = None
    app.state.auto_run_lock = asyncio.Lock()
    app.state.league_execution_lock = threading.Lock()
    auth_limiter = RateLimiter()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:3001", "http://127.0.0.1:3001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_error(_, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_failed", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content={"error": detail})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "request_invalid", "message": "Request validation failed", "details": jsonable_encoder(exc.errors())}},
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/health")
    def api_health():
        return {"status": "ok"}

    @app.get("/v1/config")
    def public_config():
        # Public, unauthenticated: lets the browser decide whether to offer a
        # signed-out feedback/vote path or send the user straight to login,
        # without ever exposing operator usernames or the GitHub token.
        return {"auth_required": settings.auth_required}

    def request_user(authorization: str | None) -> str:
        return require_user(db, authorization)

    def mutation_username(authorization: str | None, requested: str | None) -> str:
        authenticated = authenticate_token(db, authorization)
        if settings.auth_required:
            authenticated = authenticated or request_user(authorization)
            if requested and normalize_username(requested) != authenticated:
                raise HTTPException(403, {"code": "username_mismatch", "message": "Username does not match the logged-in account"})
            return authenticated
        return normalize_username(requested or authenticated or "local")

    def auth_client_key(request: Request) -> str:
        # Caddy replaces X-Forwarded-For before proxying, so the first address
        # is safe to use here. Direct/local requests fall back to the peer.
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
        return request.client.host if request.client else "unknown"

    def enforce_auth_rate_limit(request: Request, scope: str, limit: int, window_seconds: int) -> None:
        if not auth_limiter.allow(f"{scope}:ip:{auth_client_key(request)}", limit, window_seconds):
            raise HTTPException(
                429,
                {"code": "rate_limited", "message": "Too many account attempts. Try again in a few minutes."},
            )

    @app.post("/v1/auth/register", status_code=201)
    def register(
        body: RegisterRequest,
        request: Request,
        x_alpha_operator: Annotated[str | None, Header()] = None,
    ):
        enforce_auth_rate_limit(request, "register", 8, 600)
        if settings.invite_code and not __import__("hmac").compare_digest(body.invite_code or "", settings.invite_code):
            raise HTTPException(403, {"code": "invite_invalid", "message": "A valid invite code is required"})
        try:
            username = normalize_username(body.username)
            password_hash = hash_password(body.password)
        except ValueError as exc:
            raise HTTPException(422, {"code": "account_invalid", "message": str(exc)}) from exc
        if username in settings.operator_usernames and (
            not settings.operator_token
            or not x_alpha_operator
            or not secrets.compare_digest(x_alpha_operator, settings.operator_token)
        ):
            # Prevent a cohort member from registering an allowlisted operator
            # name before the maintainer. Operators are provisioned via the
            # API/CLI with the server-only operator token, never through JS.
            raise HTTPException(403, {"code": "operator_required", "message": "Operator access required"})
        timestamp = now_iso()
        try:
            with db.connect() as conn:
                conn.execute(
                    "INSERT INTO users(username,password_hash,created_at,updated_at) VALUES(?,?,?,?)",
                    (username, password_hash, timestamp, timestamp),
                )
        except __import__("sqlite3").IntegrityError as exc:
            raise HTTPException(409, {"code": "username_taken", "message": "That username is already registered"}) from exc
        token, expires_at = issue_session(db, username)
        return {"username": username, "token": token, "expires_at": expires_at}

    @app.post("/v1/auth/login")
    def login(body: LoginRequest, request: Request):
        enforce_auth_rate_limit(request, "login", 20, 300)
        try:
            username = normalize_username(body.username)
        except ValueError:
            username = ""
        user = db.one("SELECT password_hash FROM users WHERE username=?", (username,))
        password_ok = verify_password(body.password, user["password_hash"] if user else DUMMY_PASSWORD_HASH)
        if not user or not password_ok:
            account_key = hashlib.sha256((username or "invalid").encode("utf-8")).hexdigest()[:16]
            if not auth_limiter.allow(f"login_failure:account:{account_key}", 10, 900):
                raise HTTPException(
                    429,
                    {"code": "rate_limited", "message": "Too many account attempts. Try again in a few minutes."},
                )
            raise HTTPException(401, {"code": "credentials_invalid", "message": "Username or password is incorrect"})
        token, expires_at = issue_session(db, username)
        return {"username": username, "token": token, "expires_at": expires_at}

    @app.get("/v1/auth/me")
    def auth_me(authorization: Annotated[str | None, Header()] = None):
        username = request_user(authorization)
        return {"username": username, "is_operator": is_operator_username(settings, username)}

    @app.post("/v1/auth/logout", status_code=204)
    def logout(authorization: Annotated[str | None, Header()] = None):
        request_user(authorization)
        revoke_session(db, authorization)
        return None

    def league_snapshot() -> dict[str, Any]:
        run = db.one("SELECT * FROM runs ORDER BY requested_at DESC LIMIT 1")
        active_count = int(db.one("SELECT count(*) AS n FROM submissions WHERE active=1")["n"])
        queue = db.one("SELECT requested_generation,completed_generation,running,updated_at FROM league_queue WHERE singleton=1")
        pending = int(queue["requested_generation"]) > int(queue["completed_generation"])
        running = bool(queue["running"] and run and run["status"] in {"queued", "running"})
        if running:
            state = "running"
            message = "The league is playing now. Standings will refresh when it finishes."
        elif pending and active_count < 2:
            state = "waiting_for_players"
            needed = 2 - active_count
            message = f"Waiting for {needed} more active bot{'s' if needed != 1 else ''} before the next league run."
        elif pending:
            state = "queued"
            message = "The next league run is queued and will begin shortly."
        elif run and run["status"] == "failed":
            state = "failed"
            message = "The latest league run failed. A new accepted upload will retry the league."
        elif run and run["status"] == "completed":
            state = "completed"
            message = "The latest league run is complete."
        else:
            state = "idle"
            message = "The league is ready for bot submissions."
        if run:
            run["progress"] = {
                "matchups_completed": int(run.get("completed_matchups") or 0),
                "matchups_total": int(run.get("total_matchups") or 0),
            }
        return {
            "name": "Alpha Poker", "format": "heads-up no-limit hold'em", "play_money_only": True,
            "bot_count": active_count, "minimum_bots": 2, "current_run": run,
            "schedule": "after each accepted upload",
            "rules": {"starting_stack": 10000, "small_blind": 50, "big_blind": 100, "seat_mirroring": True},
            "queue": {
                **queue, "pending": pending, "running": running, "state": state, "message": message,
                "active_bot_count": active_count, "minimum_bot_count": 2,
            },
        }

    @app.get("/v1/league")
    def league():
        return league_snapshot()

    @app.get("/v1/account/status")
    def account_status(authorization: Annotated[str | None, Header()] = None):
        username = request_user(authorization)
        latest = db.one("SELECT * FROM submissions WHERE username=? ORDER BY created_at DESC LIMIT 1", (username,))
        active = db.one("SELECT * FROM submissions WHERE username=? AND active=1 ORDER BY created_at DESC LIMIT 1", (username,))
        result = None
        if active:
            result = db.one(
                "SELECT r.*,l.rank,l.elo_rating,l.matchup_wins,l.matchup_losses,l.matchup_draws "
                "FROM leaderboard l JOIN runs r ON r.id=l.run_id "
                "WHERE l.submission_id=? AND r.status='completed' AND r.official=1 "
                "ORDER BY r.completed_at DESC LIMIT 1",
                (active["id"],),
            )
        league_status = league_snapshot()
        if not latest:
            participant_state = "no_submission"
            participant_message = "No bot submitted yet."
        elif latest["status"] in {"queued", "validating"}:
            participant_state = "validating"
            participant_message = "Your bot is being checked before it enters the league."
        elif latest["status"] == "rejected":
            participant_state = "rejected"
            participant_message = "Your bot did not pass validation. Open the validation log for details."
        else:
            participant_state = league_status["queue"]["state"]
            participant_message = league_status["queue"]["message"]
        return {
            "username": username,
            "is_operator": is_operator_username(settings, username),
            "participant_state": participant_state,
            "participant_message": participant_message,
            "submission": public_submission(latest) if latest else None,
            "active_submission": public_submission(active) if active else None,
            "league": league_status,
            "result": ({
                **result,
                "record": {
                    "wins": result["matchup_wins"], "losses": result["matchup_losses"],
                    "draws": result["matchup_draws"],
                },
                "artifacts_url": f"/v1/runs/{result['id']}/artifacts",
            } if result else None),
            "submission_logs_url": f"/v1/submissions/{latest['id']}/logs" if latest else None,
        }

    @app.get("/v1/leaderboard")
    def leaderboard():
        run = db.one("SELECT * FROM runs WHERE status='completed' ORDER BY completed_at DESC LIMIT 1")
        if not run:
            return {"run_id": None, "updated_at": None, "entries": []}
        rows = db.all("SELECT * FROM leaderboard WHERE run_id=? ORDER BY rank", (run["id"],))
        entries = [{
            "rank": r["rank"], "username": r["username"], "bot_name": r["bot_name"],
            "elo_rating": r["elo_rating"],
            "matchup_wins": r["matchup_wins"], "matchup_losses": r["matchup_losses"],
            "matchup_draws": r["matchup_draws"],
            "bb_per_100": r["bb_per_100"], "confidence_95": [r["ci_low"], r["ci_high"]], "hands": r["hands"],
        } for r in rows]
        return {"run_id": run["id"], "updated_at": run["completed_at"], "entries": entries}

    @app.get("/v1/matchups")
    def matchups():
        run = db.one("SELECT id FROM runs WHERE status='completed' ORDER BY completed_at DESC LIMIT 1")
        return {"run_id": run["id"] if run else None, "matchups": _matchups(run["id"]) if run else []}

    def _matchups(run_id: str):
        return [{
            "matchup_id": r["id"], "player_a": r["player_a"], "player_b": r["player_b"],
            "hands": r["hands"], "player_a_bb_per_100": r["player_a_bb_per_100"],
            "confidence_95": [r["ci_low"], r["ci_high"]], "wins_a": r["wins_a"],
            "wins_b": r["wins_b"], "ties": r["ties"],
        } for r in db.all("SELECT * FROM matchups WHERE run_id=? ORDER BY player_a, player_b", (run_id,))]

    @app.get("/v1/runs")
    def runs():
        return {"runs": db.all("SELECT * FROM runs ORDER BY requested_at DESC")}

    @app.get("/v1/runs/{run_id}")
    def run_detail(run_id: str):
        run = db.one("SELECT * FROM runs WHERE id=?", (run_id,))
        if not run:
            raise HTTPException(404, {"code": "run_not_found", "message": "Run not found"})
        run["reproducibility"] = {"seed": run["seed"], "engine_version": run["engine_version"], "rules_version": run["rules_version"], "seat_mirroring": True}
        run["progress"] = {
            "matchups_completed": int(run.get("completed_matchups") or db.one("SELECT count(*) AS n FROM matchups WHERE run_id=?", (run_id,))["n"]),
            "matchups_total": int(run.get("total_matchups") or 0),
            "detailed_hands_retained": db.one("SELECT count(*) AS n FROM hands WHERE run_id=?", (run_id,))["n"],
            "artifact_available": (settings.artifact_dir / f"{run_id}.zip").exists()
            or bool(db.one("SELECT 1 FROM hands WHERE run_id=? LIMIT 1", (run_id,))),
        }
        return run

    @app.get("/v1/runs/{run_id}/matchups")
    def run_matchups(run_id: str):
        if not db.one("SELECT 1 FROM runs WHERE id=?", (run_id,)):
            raise HTTPException(404, {"code": "run_not_found", "message": "Run not found"})
        return {"run_id": run_id, "matchups": _matchups(run_id)}

    @app.get("/v1/runs/{run_id}/summary")
    def run_summary(run_id: str):
        if not db.one("SELECT 1 FROM runs WHERE id=?", (run_id,)):
            raise HTTPException(404, {"code": "run_not_found", "message": "Run not found"})
        stored = settings.artifact_dir / f"{run_id}.zip"
        if stored.exists():
            with zipfile.ZipFile(stored) as archive:
                return json.loads(archive.read("summary.json"))
        return summarize_run(db, run_id)

    @app.post("/v1/submissions", status_code=202)
    async def upload_submission(
        background: BackgroundTasks,
        bot_name: Annotated[str, Form(min_length=1, max_length=80)],
        package: Annotated[UploadFile, File()],
        username: Annotated[str | None, Form(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")] = None,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        authorization: Annotated[str | None, Header()] = None,
    ):
        username = mutation_username(authorization, username)
        if not package.filename or not package.filename.lower().endswith(".zip"):
            raise HTTPException(400, {"code": "submission_invalid", "message": "Package must be a ZIP file"})
        submission_id = "sub_" + (
            hashlib.sha256(f"{username}\0{idempotency_key}".encode()).hexdigest()[:16]
            if idempotency_key else secrets.token_hex(8)
        )
        existing = db.one("SELECT * FROM submissions WHERE id=?", (submission_id,))
        if existing:
            return public_submission(existing)
        destination = settings.upload_dir / f"{submission_id}.zip"
        size = 0
        digest = hashlib.sha256()
        with destination.open("wb") as output:
            while chunk := await package.read(64 * 1024):
                size += len(chunk)
                if size > MAX_ZIP_BYTES:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(413, {"code": "submission_too_large", "message": "ZIP exceeds 2 MB"})
                digest.update(chunk)
                output.write(chunk)
        timestamp = now_iso()
        db.execute(
            "INSERT INTO submissions(id,username,bot_name,original_filename,package_path,sha256,status,created_at,updated_at) VALUES(?,?,?,?,?,?,'queued',?,?)",
            (submission_id, username, bot_name, package.filename, str(destination), digest.hexdigest(), timestamp, timestamp),
        )
        background.add_task(validate_and_schedule, submission_id)
        return public_submission(db.one("SELECT * FROM submissions WHERE id=?", (submission_id,)))

    async def auto_run_worker() -> None:
        """Serialize league work and coalesce uploads that arrive mid-run."""
        async with app.state.auto_run_lock:
            while True:
                queue = db.one("SELECT * FROM league_queue WHERE singleton=1")
                target_generation = int(queue["requested_generation"])
                if target_generation <= int(queue["completed_generation"]):
                    db.execute("UPDATE league_queue SET running=0,updated_at=? WHERE singleton=1", (now_iso(),))
                    return
                active_count = db.one("SELECT count(*) AS n FROM submissions WHERE active=1")["n"]
                if active_count < 2:
                    db.execute("UPDATE league_queue SET running=0,updated_at=? WHERE singleton=1", (now_iso(),))
                    return
                run_id = "run_" + secrets.token_hex(8)
                db.execute(
                    "INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,hand_count_per_pairing) VALUES(?,'queued',1,'prototype-0.1','heads-up-v1',?,?,?)",
                    (run_id, secrets.randbelow(2**31), now_iso(), settings.auto_run_hand_count),
                )
                db.execute("UPDATE league_queue SET running=1,updated_at=? WHERE singleton=1", (now_iso(),))
                try:
                    await asyncio.to_thread(run_and_archive, run_id, settings.auto_run_hand_count)
                except asyncio.CancelledError:
                    db.execute("UPDATE league_queue SET running=0,updated_at=? WHERE singleton=1", (now_iso(),))
                    raise
                except Exception:
                    # run_official_league records the failure on the run. Keep the
                    # queue alive so a newer accepted upload can still be tried.
                    pass
                db.execute(
                    "UPDATE league_queue SET completed_generation=?,running=0,updated_at=? WHERE singleton=1",
                    (target_generation, now_iso()),
                )

    def run_and_archive(run_id: str, hand_count: int) -> None:
        with app.state.league_execution_lock:
            run_official_league(db, run_id, hand_count, settings.auto_run_timeout_seconds)
            run = db.one("SELECT status FROM runs WHERE id=?", (run_id,))
            if run and run["status"] == "completed":
                archive_run(db, run_id, settings.artifact_dir)
                archive_and_prune(
                    db,
                    settings.artifact_dir,
                    settings.retained_hand_runs,
                    settings.retained_artifact_runs,
                )
                prune_submission_packages(db)

    def request_auto_run() -> None:
        db.execute(
            "UPDATE league_queue SET requested_generation=requested_generation+1,updated_at=? WHERE singleton=1",
            (now_iso(),),
        )
        task = app.state.auto_run_task
        if task is None or task.done():
            app.state.auto_run_task = asyncio.create_task(auto_run_worker())

    async def validate_and_schedule(submission_id: str) -> None:
        def validate_with_package_lock() -> None:
            # Activation and package pruning share the same lock as official
            # execution, closing the check-then-delete window around bot ZIPs.
            with app.state.league_execution_lock:
                validate_submission(db, submission_id)

        await asyncio.to_thread(validate_with_package_lock)
        row = db.one("SELECT status FROM submissions WHERE id=?", (submission_id,))
        if not settings.auto_run_on_accept or not row or row["status"] != "accepted":
            return
        request_auto_run()

    def get_username(username: str | None, x_alpha_username: str | None, authorization: str | None) -> str:
        if settings.auth_required:
            return mutation_username(authorization, username or x_alpha_username)
        value = username or x_alpha_username
        if not value:
            raise HTTPException(400, {"code": "username_required", "message": "Pass username or X-Alpha-Username"})
        return value

    @app.get("/v1/submissions/current")
    def current_submission(username: str | None = Query(None), x_alpha_username: str | None = Header(None), authorization: str | None = Header(None)):
        value = get_username(username, x_alpha_username, authorization)
        row = db.one("SELECT * FROM submissions WHERE username=? AND active=1 ORDER BY created_at DESC LIMIT 1", (value,))
        if not row:
            raise HTTPException(404, {"code": "submission_not_found", "message": "No active submission"})
        return public_submission(row)

    @app.get("/v1/submissions/{submission_id}")
    def submission(submission_id: str, authorization: str | None = Header(None)):
        row = db.one("SELECT * FROM submissions WHERE id=?", (submission_id,))
        if not row:
            raise HTTPException(404, {"code": "submission_not_found", "message": "Submission not found"})
        if settings.auth_required and row["username"] != request_user(authorization):
            raise HTTPException(403, {"code": "submission_forbidden", "message": "Submission belongs to another account"})
        return public_submission(row)

    @app.get("/v1/submissions/{submission_id}/logs")
    def submission_logs(submission_id: str, authorization: str | None = Header(None)):
        row = db.one("SELECT username,logs FROM submissions WHERE id=?", (submission_id,))
        if not row:
            raise HTTPException(404, {"code": "submission_not_found", "message": "Submission not found"})
        if settings.auth_required and row["username"] != request_user(authorization):
            raise HTTPException(403, {"code": "submission_forbidden", "message": "Submission belongs to another account"})
        return PlainTextResponse(row["logs"], media_type="text/plain")

    @app.get("/v1/hands/{hand_id}")
    def hand(hand_id: str):
        row = db.one("SELECT record_json FROM hands WHERE id=?", (hand_id,))
        if not row:
            raise HTTPException(404, {"code": "hand_not_found", "message": "Hand not found"})
        return json.loads(row["record_json"])

    @app.get("/v1/hands/{hand_id}/phh")
    def hand_phh(hand_id: str):
        row = db.one("SELECT phh FROM hands WHERE id=?", (hand_id,))
        if not row:
            raise HTTPException(404, {"code": "hand_not_found", "message": "Hand not found"})
        return PlainTextResponse(row["phh"], media_type="text/plain", headers={"Content-Disposition": f'attachment; filename="{hand_id}.phh"'})

    @app.get("/v1/runs/{run_id}/artifacts")
    def artifacts(run_id: str):
        run = db.one("SELECT status FROM runs WHERE id=?", (run_id,))
        if not run:
            raise HTTPException(404, {"code": "run_not_found", "message": "Run not found"})
        if run["status"] != "completed":
            raise HTTPException(409, {"code": "artifacts_not_ready", "message": "Run artifacts are not ready"})
        stored = settings.artifact_dir / f"{run_id}.zip"
        if stored.exists():
            return FileResponse(stored, media_type="application/zip", filename=f"{run_id}-artifacts.zip")
        if not db.one("SELECT 1 FROM hands WHERE run_id=? LIMIT 1", (run_id,)):
            raise HTTPException(410, {"code": "artifacts_expired", "message": "Run artifacts have expired"})
        content = build_run_artifact(db, run_id)
        return StreamingResponse(io.BytesIO(content), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{run_id}-artifacts.zip"'})

    @app.post("/v1/admin/runs", status_code=202)
    def start_run(
        body: RunCreate,
        background: BackgroundTasks,
        authorization: str | None = Header(None),
        x_alpha_operator: str | None = Header(None),
    ):
        if settings.auth_required:
            request_user(authorization)
            if not settings.operator_token or not x_alpha_operator or not secrets.compare_digest(
                x_alpha_operator, settings.operator_token
            ):
                raise HTTPException(
                    403,
                    {"code": "operator_required", "message": "Operator access required"},
                )
        run_id = "run_" + secrets.token_hex(8)
        db.execute(
            "INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,hand_count_per_pairing) VALUES(?,'queued',1,'prototype-0.1','heads-up-v1',?,?,?)",
            (run_id, body.seed if body.seed is not None else secrets.randbelow(2**31), now_iso(), body.hand_count_per_pairing),
        )
        background.add_task(run_and_archive, run_id, body.hand_count_per_pairing)
        return {"run_id": run_id, "status": "queued", "hand_count_per_pairing": body.hand_count_per_pairing}

    @app.post("/v1/training/sessions", status_code=201)
    def training_create(body: TrainingCreate, request: Request, authorization: str | None = Header(None)):
        username = mutation_username(authorization, body.username)
        # The published leader package is always protected by
        # prune_submission_packages, so training setup must not wait behind a
        # potentially long official round robin.
        result = create_session(db, username, body.hand_limit, body.client_schema_version)
        forwarded_scheme = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
        scheme = "wss" if request.url.scheme == "https" or forwarded_scheme == "https" else "ws"
        result["websocket_url"] = f"{scheme}://{request.url.netloc}/v1/training/ws?session_id={result['session_id']}&token={result['training_token']}"
        return result

    @app.get("/v1/training/sessions/{session_id}")
    def training_get(session_id: str, authorization: str | None = Header(None)):
        row = db.one("SELECT id,username,opponent,leader_username,hand_limit,status,schema_version,created_at,expires_at,hands_played,seq FROM training_sessions WHERE id=?", (session_id,))
        if not row:
            raise HTTPException(404, {"code": "session_not_found", "message": "Training session not found"})
        if settings.auth_required and row["username"] != request_user(authorization):
            raise HTTPException(403, {"code": "session_forbidden", "message": "Training session belongs to another account"})
        return row

    @app.delete("/v1/training/sessions/{session_id}")
    def training_stop(session_id: str, authorization: str | None = Header(None)):
        session = db.one("SELECT username FROM training_sessions WHERE id=?", (session_id,))
        if not session:
            raise HTTPException(404, {"code": "session_not_found", "message": "Training session not found"})
        if settings.auth_required and session["username"] != request_user(authorization):
            raise HTTPException(403, {"code": "session_forbidden", "message": "Training session belongs to another account"})
        db.execute("UPDATE training_sessions SET status='stopped' WHERE id=?", (session_id,))
        runtime = app.state.training_runtimes.pop(session_id, None)
        if runtime:
            runtime.close()
        return {"session_id": session_id, "status": "stopped"}

    @app.get("/v1/training/sessions/{session_id}/artifacts")
    def training_artifacts(session_id: str, authorization: str | None = Header(None)):
        session = db.one("SELECT id,username,leader_username,status,hands_played,created_at FROM training_sessions WHERE id=?", (session_id,))
        if not session:
            raise HTTPException(404, {"code": "session_not_found", "message": "Training session not found"})
        if settings.auth_required and session["username"] != request_user(authorization):
            raise HTTPException(403, {"code": "session_forbidden", "message": "Training session belongs to another account"})
        events = db.all("SELECT seq,payload FROM training_events WHERE session_id=? ORDER BY seq", (session_id,))
        hands = db.all("SELECT record_json FROM training_hands WHERE session_id=? ORDER BY hand_number", (session_id,))
        profits = db.all("SELECT client_profit FROM training_hands WHERE session_id=?", (session_id,))
        session["client_profit_chips"] = sum(row["client_profit"] for row in profits)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("summary.json", json.dumps(session, indent=2))
            archive.writestr("events.jsonl", "".join(row["payload"] + "\n" for row in events))
            archive.writestr("hands.jsonl", "".join(row["record_json"] + "\n" for row in hands))
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{session_id}-artifacts.zip"'})

    @app.websocket("/v1/training/ws")
    async def training_ws(websocket: WebSocket, session_id: str, token: str, after_seq: int = 0):
        session = db.one("SELECT * FROM training_sessions WHERE id=? AND token=?", (session_id, token))
        if not session:
            await websocket.close(code=4401, reason="Invalid training token")
            return
        if session["expires_at"] <= now_iso():
            await websocket.close(code=4401, reason="Training token expired")
            return
        if session["status"] in {"stopped", "completed"}:
            await websocket.close(code=4409, reason="Session is not active")
            return
        await websocket.accept()
        for row in db.all("SELECT payload FROM training_events WHERE session_id=? AND seq>? ORDER BY seq", (session_id, after_seq)):
            await websocket.send_json(json.loads(row["payload"]))
        runtime = app.state.training_runtimes.get(session_id)
        if runtime is None:
            runtime = build_runtime(db, session)
            app.state.training_runtimes[session_id] = runtime

        async def send_observed() -> None:
            for action in await advance_leader(runtime):
                await websocket.send_json(emit(db, session_id, "action.observed", action))

        async def next_request() -> dict[str, Any] | None:
            nonlocal session
            session = db.one("SELECT * FROM training_sessions WHERE id=?", (session_id,))
            while int(session["hands_played"]) < int(session["hand_limit"]):
                if runtime.hand is None or runtime.hand.finished:
                    start_hand(runtime, session)
                    await websocket.send_json(emit(db, session_id, "hand.started", {
                        "hand_id": runtime.hand.hand_id, "hand_number": runtime.hand.hand_number,
                        "client_seat": runtime.client_seat, "button_seat": runtime.hand.dealer,
                    }))
                await send_observed()
                if runtime.hand.finished:
                    history = persist_completed_hand(db, runtime)
                    await websocket.send_json(emit(db, session_id, "hand.completed", {
                        "hand_id": history["hand_id"], "client_profit": history["client_profit"],
                    }))
                    session = db.one("SELECT * FROM training_sessions WHERE id=?", (session_id,))
                    continue
                return action_request(db, session_id, runtime.hand.bot_state(runtime.client_seat))
            db.execute("UPDATE training_sessions SET status='completed' WHERE id=?", (session_id,))
            completed = emit(db, session_id, "session.completed", {
                "reason": "hand_limit", "hands_played": session["hands_played"],
                "artifacts_url": f"/v1/training/sessions/{session_id}/artifacts",
            })
            await websocket.send_json(completed)
            runtime.close()
            app.state.training_runtimes.pop(session_id, None)
            await websocket.close(code=1000)
            return None

        if int(session["seq"]) <= after_seq or int(session["seq"]) == 0:
            db.execute("UPDATE training_sessions SET status='running' WHERE id=?", (session_id,))
            await websocket.send_json(emit(db, session_id, "connection.ready", {"reconnect_window_seconds": 120}))
            await websocket.send_json(emit(db, session_id, "session.started", {"opponent": session["leader_username"], "hand_limit": session["hand_limit"]}))
            request_event = await next_request()
            if request_event is None:
                return
            await websocket.send_json(request_event)
        else:
            request_event = json.loads(db.one("SELECT payload FROM training_events WHERE session_id=? AND payload LIKE '%action.requested%' ORDER BY seq DESC LIMIT 1", (session_id,))["payload"])
        try:
            while True:
                try:
                    message = await asyncio.wait_for(websocket.receive_json(), timeout=1.25)
                except TimeoutError:
                    response = emit(db, session_id, "action.rejected", {"code": "bot_timeout", "message": "Action deadline elapsed"})
                    await websocket.send_json(response)
                    runtime.hand.events.append({
                        "type": "bot_error", "seat": runtime.client_seat,
                        "street": runtime.hand.street, "error": "decision timed out",
                        "fallback": "forfeit", "elapsed_ms_upper_bound": 1250,
                    })
                    runtime.hand.forfeit(runtime.client_seat)
                    history = persist_completed_hand(db, runtime)
                    await websocket.send_json(emit(db, session_id, "hand.completed", {"hand_id": history["hand_id"], "client_profit": history["client_profit"]}))
                    request_event = await next_request()
                    if request_event is None:
                        return
                    await websocket.send_json(request_event)
                    continue
                if message.get("type") == "resync.request":
                    await websocket.send_json(emit(db, session_id, "state.snapshot", {"status": "running", "last_request": request_event}))
                    continue
                if message.get("type") == "session.stop":
                    db.execute("UPDATE training_sessions SET status='stopped' WHERE id=?", (session_id,))
                    await websocket.send_json(emit(db, session_id, "session.completed", {"reason": "client_stopped"}))
                    runtime.close()
                    app.state.training_runtimes.pop(session_id, None)
                    await websocket.close(code=1000)
                    return
                if message.get("type") != "action.submit":
                    await websocket.send_json({"type": "error", "error": {"code": "message_invalid", "message": "Unknown message type"}})
                    continue
                action_id = message.get("client_action_id")
                if not action_id:
                    await websocket.send_json({"type": "action.rejected", "error": {"code": "action_invalid", "message": "client_action_id is required"}})
                    continue
                previous = remembered_action(db, session_id, action_id)
                if previous:
                    await websocket.send_json(previous)
                    continue
                expected = request_event["payload"]
                if message.get("hand_id") != expected["hand_id"] or message.get("turn_id") != expected["turn_id"] or message.get("turn_token") != expected["turn_token"]:
                    response = {"type": "action.rejected", "seq": request_event["seq"], "error": {"code": "stale_turn", "message": "Turn ID or token is stale"}}
                    remember_action(db, session_id, action_id, response)
                    await websocket.send_json(response)
                    continue
                try:
                    engine_action = public_action_to_engine(message, expected["state"])
                except ValueError as exc:
                    response = {"type": "action.rejected", "seq": request_event["seq"], "error": {"code": "action_invalid", "message": str(exc)}}
                    remember_action(db, session_id, action_id, response)
                    await websocket.send_json(response)
                    runtime.hand.events.append({
                        "type": "bot_error", "seat": runtime.client_seat,
                        "street": runtime.hand.street, "error": str(exc),
                        "fallback": "forfeit", "elapsed_ms_upper_bound": 0,
                    })
                    runtime.hand.forfeit(runtime.client_seat)
                    history = persist_completed_hand(db, runtime)
                    await websocket.send_json(emit(db, session_id, "hand.completed", {"hand_id": history["hand_id"], "client_profit": history["client_profit"]}))
                    request_event = await next_request()
                    if request_event is None:
                        return
                    await websocket.send_json(request_event)
                    continue
                action = message.get("action")
                runtime.hand.act(engine_action)
                response = emit(db, session_id, "action.accepted", {"client_action_id": action_id, "action": action, "amount": message.get("amount")})
                remember_action(db, session_id, action_id, response)
                await websocket.send_json(response)
                await send_observed()
                if runtime.hand.finished:
                    history = persist_completed_hand(db, runtime)
                    await websocket.send_json(emit(db, session_id, "hand.completed", {"hand_id": history["hand_id"], "client_profit": history["client_profit"]}))
                request_event = await next_request()
                if request_event is None:
                    return
                await websocket.send_json(request_event)
        except WebSocketDisconnect:
            return

    register_community_routes(app, db, settings)
    return app


app = create_app()
