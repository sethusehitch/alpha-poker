import io
import json
from pathlib import Path
import time
import zipfile
from datetime import UTC, datetime, timedelta
import pytest

from fastapi.testclient import TestClient

from alpha_poker_api.config import Settings
from alpha_poker_api.db import Database, now_iso
from alpha_poker_api.main import create_app
from alpha_poker_api import jobs


def package(action: str) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(
            "bot.py",
            f"def decide(state):\n    if '{action}' in state['legal_actions']:\n        return {{'action':'{action}'}}\n    return {{'action':'check' if 'check' in state['legal_actions'] else 'call'}}\n",
        )
        archive.writestr(
            "bot.json",
            json.dumps({"api_version": "2026-09-01", "name": action, "language": "python", "entrypoint": "bot.py:decide"}),
        )
    return data.getvalue()


def settings_for(tmp_path, *, auto: bool, retained: int = 2, artifacts: int = 30):
    return Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=False,
        auto_run_on_accept=auto,
        auto_run_hand_count=2,
        retained_hand_runs=retained,
        retained_artifact_runs=artifacts,
    )


def accepted_submissions(client):
    for username, action in (("alice", "call"), ("bob", "fold")):
        response = client.post(
            "/v1/submissions",
            data={"username": username, "bot_name": username},
            files={"package": ("bot.zip", package(action), "application/zip")},
        )
        assert response.status_code == 202


def test_pending_queue_recovers_after_api_restart(tmp_path):
    initial = settings_for(tmp_path, auto=False)
    with TestClient(create_app(initial)) as client:
        accepted_submissions(client)
    db = Database(initial.database_path)
    db.execute(
        "UPDATE league_queue SET requested_generation=1,completed_generation=0,running=1,updated_at=? WHERE singleton=1",
        (now_iso(),),
    )

    recovered = settings_for(tmp_path, auto=True)
    with TestClient(create_app(recovered)) as client:
        deadline = time.monotonic() + 3
        board = {"entries": []}
        while time.monotonic() < deadline:
            board = client.get("/v1/leaderboard").json()
            queue = client.app.state.db.one("SELECT * FROM league_queue WHERE singleton=1")
            if len(board["entries"]) == 2 and queue["completed_generation"] == 1:
                break
            time.sleep(0.01)
        assert len(board["entries"]) == 2
        queue = client.app.state.db.one("SELECT * FROM league_queue WHERE singleton=1")
        assert queue["completed_generation"] == 1
        assert queue["running"] == 0


def test_old_hand_rows_are_archived_and_artifact_count_is_bounded(tmp_path):
    settings = settings_for(tmp_path, auto=False, retained=1, artifacts=2)
    with TestClient(create_app(settings)) as client:
        accepted_submissions(client)
        run_ids = []
        for seed in (11, 12, 13):
            response = client.post(
                "/v1/admin/runs", json={"hand_count_per_pairing": 2, "seed": seed}
            )
            assert response.status_code == 202
            run_ids.append(response.json()["run_id"])

        hands_by_run = {
            row["run_id"]: row["n"]
            for row in client.app.state.db.all("SELECT run_id,count(*) AS n FROM hands GROUP BY run_id")
        }
        assert set(hands_by_run) == {run_ids[-1]}
        assert hands_by_run[run_ids[-1]] > 0
        assert client.get(f"/v1/runs/{run_ids[0]}/artifacts").status_code == 410
        artifact = client.get(f"/v1/runs/{run_ids[1]}/artifacts")
        assert artifact.status_code == 200
        with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
            assert len(archive.read("hands.jsonl").splitlines()) > 0
            summary = json.loads(archive.read("summary.json"))
            assert summary["players"]
            assert summary["methodology"]["format"] == "heads-up pot-limit hold'em tournament games"


def test_time_based_cleanup_keeps_latest_three_official_runs_and_summaries(tmp_path):
    settings = settings_for(tmp_path, auto=False, retained=4, artifacts=10)
    with TestClient(create_app(settings)) as client:
        accepted_submissions(client)
        run_ids = [
            client.post("/v1/admin/runs", json={"seed": seed}).json()["run_id"]
            for seed in (31, 32, 33, 34)
        ]
        old = (datetime.now(UTC) - timedelta(days=45)).isoformat().replace("+00:00", "Z")
        for run_id in run_ids:
            client.app.state.db.execute("UPDATE runs SET completed_at=? WHERE id=?", (old, run_id))
        preview = jobs.cleanup_raw_histories(
            client.app.state.db, settings.artifact_dir, now=datetime.now(UTC), dry_run=True
        )
        assert set(preview["official_runs"]) == {run_ids[0]}
        assert client.app.state.db.one("SELECT COUNT(*) AS n FROM hands WHERE run_id=?", (run_ids[0],))["n"] > 0
        removed = jobs.cleanup_raw_histories(
            client.app.state.db, settings.artifact_dir, now=datetime.now(UTC), dry_run=False
        )
        assert set(removed["official_runs"]) == {run_ids[0]}
        assert client.app.state.db.one("SELECT COUNT(*) AS n FROM hands WHERE run_id=?", (run_ids[0],))["n"] == 0
        assert (settings.artifact_dir / f"{run_ids[0]}.zip").exists()
        assert client.app.state.db.one("SELECT COUNT(*) AS n FROM leaderboard WHERE run_id=?", (run_ids[0],))["n"] == 2


def test_time_based_cleanup_archives_old_challenge_hands_but_keeps_result(tmp_path):
    settings = settings_for(tmp_path, auto=False, retained=4, artifacts=10)
    with TestClient(create_app(settings)) as client:
        accepted_submissions(client)
        timestamp = now_iso()
        for username in ("alice", "bob"):
            client.app.state.db.execute(
                "INSERT INTO users(username,password_hash,created_at,updated_at) VALUES(?,?,?,?)",
                (username, "test-only", timestamp, timestamp),
            )
        alice = client.app.state.db.one("SELECT id FROM submissions WHERE username='alice' AND active=1")["id"]
        bob = client.app.state.db.one("SELECT id FROM submissions WHERE username='bob' AND active=1")["id"]
        client.app.state.db.execute(
            "INSERT INTO rival_challenges(id,challenger_username,challenged_username,challenger_submission_id,"
            "challenged_submission_id,status,hand_count,seed,created_at,accepted_at,updated_at) "
            "VALUES('old_challenge','alice','bob',?,?,'queued',200,77,?,?,?)",
            (alice, bob, timestamp, timestamp, timestamp),
        )
        assert jobs.run_rival_challenge(client.app.state.db, "old_challenge")
        challenge = client.app.state.db.one("SELECT * FROM rival_challenges WHERE id='old_challenge'")
        run_id = challenge["run_id"]
        old = (datetime.now(UTC) - timedelta(days=100)).isoformat().replace("+00:00", "Z")
        client.app.state.db.execute("UPDATE runs SET completed_at=? WHERE id=?", (old, run_id))
        removed = jobs.cleanup_raw_histories(
            client.app.state.db, settings.artifact_dir, now=datetime.now(UTC), dry_run=False
        )
        assert removed["challenge_runs"] == [run_id]
        assert client.app.state.db.one("SELECT COUNT(*) AS n FROM hands WHERE run_id=?", (run_id,))["n"] == 0
        assert client.app.state.db.one("SELECT status,series_score_a,series_score_b FROM rival_challenges WHERE id='old_challenge'") == {
            "status": "completed", "series_score_a": challenge["series_score_a"], "series_score_b": challenge["series_score_b"]
        }
        assert (settings.artifact_dir / f"{run_id}.zip").exists()


def test_time_based_cleanup_removes_only_old_training_scratch_rows(tmp_path):
    settings = settings_for(tmp_path, auto=False)
    with TestClient(create_app(settings)) as client:
        old = (datetime.now(UTC) - timedelta(days=15)).isoformat().replace("+00:00", "Z")
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        client.app.state.db.execute(
            "INSERT INTO training_sessions(id,username,opponent,leader_username,hand_limit,status,token,schema_version,created_at,expires_at) "
            "VALUES('old_training','learner','leader','leader',400,'completed','old-token','2026-09-01',?,?)",
            (old, future),
        )
        client.app.state.db.execute(
            "INSERT INTO training_events(session_id,seq,payload) VALUES('old_training',1,'{}')"
        )
        client.app.state.db.execute(
            "INSERT INTO training_actions(session_id,client_action_id,response) VALUES('old_training','action-1','{}')"
        )
        client.app.state.db.execute(
            "INSERT INTO training_hands(session_id,hand_number,hand_id,client_seat,client_profit,record_json) "
            "VALUES('old_training',1,'hand-1',0,25,'{}')"
        )
        preview = jobs.cleanup_raw_histories(
            client.app.state.db, settings.artifact_dir, now=datetime.now(UTC), dry_run=True
        )
        assert preview["training_sessions"] == ["old_training"]
        assert client.app.state.db.one("SELECT COUNT(*) AS n FROM training_hands WHERE session_id='old_training'")["n"] == 1
        jobs.cleanup_raw_histories(
            client.app.state.db, settings.artifact_dir, now=datetime.now(UTC), dry_run=False
        )
        assert client.app.state.db.one("SELECT COUNT(*) AS n FROM training_events WHERE session_id='old_training'")["n"] == 0
        assert client.app.state.db.one("SELECT COUNT(*) AS n FROM training_actions WHERE session_id='old_training'")["n"] == 0
        assert client.app.state.db.one("SELECT COUNT(*) AS n FROM training_hands WHERE session_id='old_training'")["n"] == 0
        assert client.app.state.db.one("SELECT status FROM training_sessions WHERE id='old_training'")["status"] == "completed"


def test_inactive_packages_are_pruned_after_published_leader_moves(tmp_path):
    settings = settings_for(tmp_path, auto=False)
    with TestClient(create_app(settings)) as client:
        accepted_submissions(client)
        first = client.app.state.db.one(
            "SELECT id,package_path FROM submissions WHERE username='alice' AND active=1"
        )
        first_path = Path(first["package_path"])
        assert first_path.exists()

        initial_run = client.post(
            "/v1/admin/runs", json={"hand_count_per_pairing": 2, "seed": 21}
        )
        assert initial_run.status_code == 202
        leader = client.app.state.db.one(
            "SELECT * FROM leaderboard ORDER BY rank LIMIT 1"
        )
        assert leader["username"] == "alice"
        assert leader["submission_id"] == first["id"]

        replacement = client.post(
            "/v1/submissions",
            data={"username": "alice", "bot_name": "alice-v2"},
            files={"package": ("bot.zip", package("call"), "application/zip")},
        )
        assert replacement.status_code == 202
        replacement_row = client.app.state.db.one(
            "SELECT package_path FROM submissions WHERE id=?",
            (replacement.json()["submission_id"],),
        )
        assert first_path.exists()
        assert Path(replacement_row["package_path"]).exists()

        next_run = client.post(
            "/v1/admin/runs", json={"hand_count_per_pairing": 2, "seed": 22}
        )
        assert next_run.status_code == 202
        assert not first_path.exists()

        rejected = client.post(
            "/v1/submissions",
            data={"username": "alice", "bot_name": "broken"},
            files={"package": ("bot.zip", b"not a zip", "application/zip")},
        )
        rejected_row = client.app.state.db.one(
            "SELECT package_path,status FROM submissions WHERE id=?",
            (rejected.json()["submission_id"],),
        )
        assert rejected_row["status"] == "rejected"
        assert not Path(rejected_row["package_path"]).exists()


def test_official_run_deadline_records_an_actionable_failure(tmp_path, monkeypatch):
    settings = settings_for(tmp_path, auto=False)
    with TestClient(create_app(settings)) as client:
        accepted_submissions(client)
        run_id = "run_deadline"
        client.app.state.db.execute(
            "INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,hand_count_per_pairing) "
            "VALUES(?,'queued',1,'prototype-0.1','heads-up-v1',?,?,?)",
            (run_id, 42, now_iso(), 2),
        )
        readings = iter((0.0, 31.0))
        monkeypatch.setattr(jobs, "monotonic", lambda: next(readings))
        with pytest.raises(TimeoutError, match="30-second run deadline"):
            jobs.run_official_league(client.app.state.db, run_id, 2, timeout_seconds=30)
        run = client.app.state.db.one("SELECT * FROM runs WHERE id=?", (run_id,))
        assert run["status"] == "failed"
        assert "30-second run deadline" in run["error"]
        assert run["completed_at"]
