import time
from pathlib import Path
import io
import json
import zipfile

from fastapi.testclient import TestClient

from alpha_poker_api.config import Settings
from alpha_poker_api.db import Database, now_iso
from alpha_poker_api.jobs import prune_submission_packages, run_rival_challenge
from alpha_poker_api.main import create_app
from test_rivals_api import bot_zip, participant


def settings_for(tmp_path):
    return Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=False,
        auth_required=True,
    )


def test_queued_snapshots_are_retained_and_restart_recovers_running_work(tmp_path):
    settings = settings_for(tmp_path)
    with TestClient(create_app(settings)) as client:
        participant(client, "alice", "call")
        participant(client, "bob", "fold")
        db = client.app.state.db
        alice = db.one("SELECT id,package_path FROM submissions WHERE username='alice' AND active=1")
        bob = db.one("SELECT id,package_path FROM submissions WHERE username='bob' AND active=1")
        timestamp = now_iso()
        db.execute(
            "INSERT INTO rival_challenges(id,challenger_username,challenged_username,challenger_submission_id,"
            "challenged_submission_id,status,hand_count,seed,created_at,accepted_at,started_at,updated_at) "
            "VALUES('restart_me','alice','bob',?,?,'running',200,44,?,?,?,?)",
            (alice["id"], bob["id"], timestamp, timestamp, timestamp, timestamp),
        )
        db.execute("UPDATE submissions SET active=0 WHERE id IN (?,?)", (alice["id"], bob["id"]))
        assert prune_submission_packages(db) == []
        assert Path(alice["package_path"]).exists()
        assert Path(bob["package_path"]).exists()

    with TestClient(create_app(settings)) as restarted:
        deadline = time.monotonic() + 20
        row = None
        while time.monotonic() < deadline:
            row = restarted.app.state.db.one("SELECT * FROM rival_challenges WHERE id='restart_me'")
            if row["status"] in {"completed", "failed"}:
                break
            time.sleep(0.02)
        assert row["status"] == "completed"
        assert row["run_id"]
        assert restarted.app.state.db.one(
            "SELECT COUNT(*) AS n FROM hands WHERE run_id=?", (row["run_id"],)
        )["n"] == row["hands_played"]
        artifact_path = settings.artifact_dir / f"{row['run_id']}.zip"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not artifact_path.exists():
            time.sleep(0.01)
        assert artifact_path.exists()


def test_direct_challenge_does_not_change_existing_elo(tmp_path):
    settings = settings_for(tmp_path)
    with TestClient(create_app(settings)) as client:
        alice_headers = participant(client, "alice", "call")
        bob_headers = participant(client, "bob", "fold")
        db = client.app.state.db
        timestamp = now_iso()
        alice_sub = db.one("SELECT id FROM submissions WHERE username='alice' AND active=1")["id"]
        bob_sub = db.one("SELECT id FROM submissions WHERE username='bob' AND active=1")["id"]
        db.execute(
            "INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,completed_at) "
            "VALUES('rating_baseline','completed',1,'x','x',1,?,?)", (timestamp, timestamp)
        )
        db.execute(
            "INSERT INTO leaderboard(run_id,rank,username,bot_name,bb_per_100,ci_low,ci_high,hands,submission_id,"
            "elo_rating,matchup_wins,matchup_losses,matchup_draws) VALUES"
            "('rating_baseline',1,'alice','alice-bot',1,0,2,200,?,1337,1,0,0)", (alice_sub,)
        )
        db.execute(
            "INSERT INTO leaderboard(run_id,rank,username,bot_name,bb_per_100,ci_low,ci_high,hands,submission_id,"
            "elo_rating,matchup_wins,matchup_losses,matchup_draws) VALUES"
            "('rating_baseline',2,'bob','bob-bot',-1,-2,0,200,?,1163,0,1,0)", (bob_sub,)
        )
        created = client.post("/v1/challenges", headers=alice_headers, json={"opponent_username": "bob"}).json()
        client.post(f"/v1/challenges/{created['challenge_id']}/accept", headers=bob_headers)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if client.get(f"/v1/challenges/{created['challenge_id']}", headers=alice_headers).json()["status"] == "completed":
                break
            time.sleep(0.02)
        ratings = db.all("SELECT username,elo_rating FROM leaderboard WHERE run_id='rating_baseline' ORDER BY username")
        assert ratings == [{"username": "alice", "elo_rating": 1337}, {"username": "bob", "elo_rating": 1163}]
        assert db.one("SELECT COUNT(*) AS n FROM leaderboard WHERE run_id!='rating_baseline'")["n"] == 0
        completed = db.one("SELECT * FROM rival_challenges WHERE id=?", (created["challenge_id"],))
        run_id = completed["run_id"]
        hand_id = db.one("SELECT id FROM hands WHERE run_id=? LIMIT 1", (run_id,))["id"]
        carol_headers = participant(client, "carol", "call")
        for path in (
            f"/v1/runs/{run_id}", f"/v1/runs/{run_id}/matchups",
            f"/v1/runs/{run_id}/summary", f"/v1/runs/{run_id}/artifacts",
            f"/v1/hands/{hand_id}", f"/v1/hands/{hand_id}/phh",
        ):
            assert client.get(path, headers=carol_headers).status_code == 403
            assert client.get(path, headers=alice_headers).status_code == 200
        assert all(run["id"] != run_id for run in client.get("/v1/runs").json()["runs"])
        assert client.get("/v1/leaderboard").json()["run_id"] == "rating_baseline"
        assert client.get("/v1/matchups").json()["run_id"] == "rating_baseline"
        assert client.get("/v1/league").json()["current_run"]["id"] == "rating_baseline"


def test_completed_run_is_finalized_after_restart_without_replay(tmp_path):
    settings = settings_for(tmp_path)
    with TestClient(create_app(settings)) as client:
        alice_headers = participant(client, "alice", "call")
        bob_headers = participant(client, "bob", "fold")
        created = client.post("/v1/challenges", headers=alice_headers, json={"opponent_username": "bob"}).json()
        client.post(f"/v1/challenges/{created['challenge_id']}/accept", headers=bob_headers)
        deadline = time.monotonic() + 20
        completed = None
        while time.monotonic() < deadline:
            completed = client.app.state.db.one("SELECT * FROM rival_challenges WHERE id=?", (created["challenge_id"],))
            if completed["status"] == "completed":
                break
            time.sleep(0.02)
        original_run = completed["run_id"]
        client.app.state.db.execute("DELETE FROM notifications WHERE challenge_id=?", (created["challenge_id"],))
        client.app.state.db.execute(
            "UPDATE rival_challenges SET status='running',winner_username=NULL,margin_play_chips=NULL WHERE id=?",
            (created["challenge_id"],),
        )

    with TestClient(create_app(settings)) as restarted:
        recovered = restarted.app.state.db.one("SELECT * FROM rival_challenges WHERE id=?", (created["challenge_id"],))
        assert recovered["status"] == "completed"
        assert recovered["run_id"] == original_run
        assert restarted.app.state.db.one("SELECT COUNT(*) AS n FROM runs WHERE id=?", (original_run,))["n"] == 1
        assert restarted.app.state.db.one(
            "SELECT COUNT(*) AS n FROM notifications WHERE challenge_id=?", (created["challenge_id"],)
        )["n"] == 2


def test_same_seed_produces_same_200_hand_result(tmp_path):
    settings = settings_for(tmp_path)
    with TestClient(create_app(settings)) as client:
        participant(client, "alice", "call")
        participant(client, "bob", "fold")
        db = client.app.state.db
        alice_sub = db.one("SELECT id FROM submissions WHERE username='alice' AND active=1")["id"]
        bob_sub = db.one("SELECT id FROM submissions WHERE username='bob' AND active=1")["id"]
        timestamp = now_iso()
        results = []
        for suffix in ("a", "b"):
            challenge_id = f"deterministic_{suffix}"
            db.execute(
                "INSERT INTO rival_challenges(id,challenger_username,challenged_username,challenger_submission_id,"
                "challenged_submission_id,status,hand_count,seed,created_at,accepted_at,updated_at) "
                "VALUES(?,'alice','bob',?,?,'queued',200,9911,?,?,?)",
                (challenge_id, alice_sub, bob_sub, timestamp, timestamp, timestamp),
            )
            assert run_rival_challenge(db, challenge_id)
            row = db.one(
                "SELECT winner_username,series_score_a,series_score_b,hands_played,run_id FROM rival_challenges WHERE id=?", (challenge_id,)
            )
            assert db.one("SELECT COUNT(*) AS n FROM hands WHERE run_id=?", (row["run_id"],))["n"] == row["hands_played"]
            results.append((row["winner_username"], row["series_score_a"], row["series_score_b"], row["hands_played"]))
        assert results[0] == results[1]


def test_rival_artifact_has_immutable_challenge_summary(tmp_path):
    settings = settings_for(tmp_path)
    with TestClient(create_app(settings)) as client:
        alice_headers = participant(client, "alice", "call")
        bob_headers = participant(client, "bob", "fold")
        created = client.post("/v1/challenges", headers=alice_headers, json={"opponent_username": "bob"}).json()
        client.post(f"/v1/challenges/{created['challenge_id']}/accept", headers=bob_headers)
        deadline = time.monotonic() + 20
        completed = None
        while time.monotonic() < deadline:
            completed = client.get(f"/v1/challenges/{created['challenge_id']}", headers=alice_headers).json()
            if completed["status"] == "completed":
                break
            time.sleep(0.02)
        artifact = client.get(completed["artifacts_url"], headers=alice_headers)
        assert artifact.status_code == 200
        with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
            summary = json.loads(archive.read("summary.json"))
            assert len(archive.read("hands.jsonl").splitlines()) == completed["hands_played"]
            assert set(archive.namelist()) == {"result.txt", "summary.json", "hands.phhs", "hands.jsonl"}
        assert summary["kind"] == "direct_rival_challenge"
        assert summary["challenge_id"] == created["challenge_id"]
        assert summary["official"] is False
        assert summary["ranked"] is False
        assert summary["affects_elo"] is False
        assert summary["play_money_only"] is True
        assert summary["outcome"]["winner_username"] == completed["winner_username"]
        assert summary["outcome"]["series_score"] == completed["series_score"]
        assert summary["outcome"]["hands"] == completed["hands_played"]
        assert summary["players"]["alice"]["bot_name"] == "alice-bot"
        assert summary["players"]["bob"]["bot_name"] == "bob-bot"
        assert summary["methodology"]["format"].startswith("best-of-five")
        assert "double every 10 hands" in summary["methodology"]["blinds"]
        assert "sudden death" in summary["methodology"]["blinds"]
        assert "do not change public Elo" in summary["methodology"]["ranking_effect"]

        # Changing the active bots later cannot rewrite the already archived
        # challenge snapshot or its notification facts.
        before_notifications = client.get("/v1/notifications", headers=alice_headers).json()["items"]
        participant_upload = client.post(
            "/v1/submissions",
            headers=alice_headers,
            data={"username": "alice", "bot_name": "alice-new-bot"},
            files={"package": ("bot.zip", bot_zip("call"), "application/zip")},
        )
        assert participant_upload.status_code == 202
        artifact_after = client.get(completed["artifacts_url"], headers=alice_headers)
        with zipfile.ZipFile(io.BytesIO(artifact_after.content)) as archive:
            summary_after = json.loads(archive.read("summary.json"))
        assert summary_after["players"]["alice"]["bot_name"] == "alice-bot"
        after_notifications = client.get("/v1/notifications", headers=alice_headers).json()["items"]
        assert after_notifications == before_notifications


def test_worker_failure_is_private_retry_safe_and_notifies_both_players(tmp_path):
    settings = settings_for(tmp_path)
    with TestClient(create_app(settings)) as client:
        alice_headers = participant(client, "alice", "call")
        bob_headers = participant(client, "bob", "fold")
        client.app.state.db.execute(
            "UPDATE submissions SET package_path='/definitely/missing/private/bot.zip' WHERE username='alice' AND active=1"
        )
        created = client.post("/v1/challenges", headers=alice_headers, json={"opponent_username": "bob"}).json()
        client.post(f"/v1/challenges/{created['challenge_id']}/accept", headers=bob_headers)
        deadline = time.monotonic() + 5
        result = None
        while time.monotonic() < deadline:
            result = client.get(f"/v1/challenges/{created['challenge_id']}", headers=alice_headers).json()
            if result["status"] == "failed":
                break
            time.sleep(0.02)
        assert result["status"] == "failed"
        assert result["error"] == "The match could not finish. Check the details, then try a new challenge."
        assert "/definitely/" not in result["error"]
        notifications = client.app.state.db.all(
            "SELECT username,type FROM notifications WHERE challenge_id=? AND type='challenge_failed' ORDER BY username",
            (created["challenge_id"],),
        )
        assert notifications == [
            {"username": "alice", "type": "challenge_failed"},
            {"username": "bob", "type": "challenge_failed"},
        ]
