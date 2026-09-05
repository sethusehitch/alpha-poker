import io
import json
from pathlib import Path
import time
import zipfile
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
        assert hands_by_run == {run_ids[-1]: 2}
        assert client.get(f"/v1/runs/{run_ids[0]}/artifacts").status_code == 410
        artifact = client.get(f"/v1/runs/{run_ids[1]}/artifacts")
        assert artifact.status_code == 200
        with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
            assert len(archive.read("hands.jsonl").splitlines()) == 2
            summary = json.loads(archive.read("summary.json"))
            assert summary["players"]
            assert "more hands" in summary["confidence_note"] or "separated" in summary["confidence_note"]


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
