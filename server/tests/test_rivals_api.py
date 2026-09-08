import io
import json
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from alpha_poker_api.config import Settings
from alpha_poker_api.db import now_iso
from alpha_poker_api.main import create_app


def bot_zip(action: str) -> bytes:
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


def auth_client(tmp_path):
    return TestClient(create_app(Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=False,
        auth_required=True,
    )))


def test_seeded_leaderboard_rivals_have_viewable_details(tmp_path):
    """Every player returned by the demo leaderboard can be opened in Rivals."""
    with TestClient(create_app(Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=True,
        auth_required=True,
    ))) as client:
        registration = client.post(
            "/v1/auth/register",
            json={"username": "previewer", "password": "correct horse"},
        )
        headers = {"Authorization": f"Bearer {registration.json()['token']}"}
        rivals = client.get("/v1/rivals?source=leaderboard", headers=headers)
        assert rivals.status_code == 200
        assert rivals.json()["items"]
        for rival in rivals.json()["items"]:
            detail = client.get(f"/v1/rivals/{rival['username']}", headers=headers)
            assert detail.status_code == 200
            assert detail.json()["rival"]["username"] == rival["username"]


def test_empty_my_rivals_exposes_elo_nearest_suggestions(tmp_path):
    """A new player gets useful choices without mixing suggestions into their history."""
    with TestClient(create_app(Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=True,
        auth_required=True,
    ))) as client:
        registration = client.post(
            "/v1/auth/register", json={"username": "newcomer", "password": "correct horse"}
        )
        headers = {"Authorization": f"Bearer {registration.json()['token']}"}

        mine = client.get("/v1/rivals?source=mine", headers=headers)
        assert mine.status_code == 200
        payload = mine.json()
        assert payload["items"] == []
        assert payload["viewer"] == {"has_active_bot": False}
        assert payload["suggested_for_elo"] == 1200
        assert [item["username"] for item in payload["suggested_items"]] == ["jules", "theo", "sam"]
        assert all(item["direct_record"]["played"] == 0 for item in payload["suggested_items"])

        explicit = client.get("/v1/rivals?source=suggested&limit=3", headers=headers).json()
        assert [item["username"] for item in explicit["items"]] == ["jules", "theo", "sam"]


def test_suggestions_use_viewer_latest_official_elo(tmp_path):
    with TestClient(create_app(Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=True,
        auth_required=True,
    ))) as client:
        registration = client.post(
            "/v1/auth/register", json={"username": "rankedviewer", "password": "correct horse"}
        )
        headers = {"Authorization": f"Bearer {registration.json()['token']}"}
        client.app.state.db.execute(
            "INSERT INTO leaderboard(run_id,rank,username,bot_name,bb_per_100,ci_low,ci_high,hands,"
            "submission_id,elo_rating,matchup_wins,matchup_losses,matchup_draws) "
            "VALUES('run_demo',6,'rankedviewer','RankedBot',0,0,0,100,NULL,1250,0,0,0)"
        )

        payload = client.get("/v1/rivals?source=mine", headers=headers).json()
        assert payload["suggested_for_elo"] == 1250
        assert [item["username"] for item in payload["suggested_items"]] == ["maya", "theo", "jules"]


def participant(client, username: str, action: str = "call") -> dict[str, str]:
    registration = client.post(
        "/v1/auth/register", json={"username": username, "password": "correct horse"}
    )
    assert registration.status_code == 201
    headers = {"Authorization": f"Bearer {registration.json()['token']}"}
    submitted = client.post(
        "/v1/submissions",
        headers=headers,
        data={"username": username, "bot_name": f"{username}-bot"},
        files={"package": ("bot.zip", bot_zip(action), "application/zip")},
    )
    assert submitted.status_code == 202
    assert client.get("/v1/submissions/current", headers=headers).status_code == 200
    return headers


def wait_for_challenge(client, challenge_id: str, headers: dict[str, str]) -> dict:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        result = client.get(f"/v1/challenges/{challenge_id}", headers=headers).json()
        if result["status"] in {"completed", "failed"}:
            return result
        time.sleep(0.02)
    raise AssertionError("challenge did not finish")


def test_accept_snapshots_immediately_while_official_execution_is_busy(tmp_path):
    with auth_client(tmp_path) as client:
        alice = participant(client, "alice", "call")
        bob = participant(client, "bob", "fold")
        created = client.post(
            "/v1/challenges", headers=alice, json={"opponent_username": "bob"}
        ).json()
        started = time.monotonic()
        with client.app.state.league_execution_lock:
            accepted = client.post(
                f"/v1/challenges/{created['challenge_id']}/accept", headers=bob
            )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "queued"
        assert time.monotonic() - started < 1
        assert wait_for_challenge(client, created["challenge_id"], bob)["status"] == "completed"


def test_auth_bot_requirements_idempotency_and_transitions(tmp_path):
    with auth_client(tmp_path) as client:
        no_bot = client.post(
            "/v1/auth/register", json={"username": "charlie", "password": "correct horse"}
        ).json()
        no_bot_headers = {"Authorization": f"Bearer {no_bot['token']}"}
        alice = participant(client, "alice")
        missing_own = client.post(
            "/v1/challenges", headers=no_bot_headers, json={"opponent_username": "alice"}
        )
        assert missing_own.status_code == 409
        assert missing_own.json()["error"]["code"] == "active_bot_required"
        missing_opponent = client.post(
            "/v1/challenges", headers=alice, json={"opponent_username": "charlie"}
        )
        assert missing_opponent.status_code == 409
        assert missing_opponent.json()["error"]["code"] == "opponent_bot_required"
        bob = participant(client, "bob", "fold")
        rivals = client.get("/v1/rivals", headers=alice)
        assert rivals.status_code == 200
        assert rivals.json()["viewer"] == {"has_active_bot": True}
        assert client.get("/v1/rivals").status_code == 401

        self_challenge = client.post("/v1/challenges", headers=alice, json={"opponent_username": "alice"})
        assert self_challenge.status_code == 400
        key_headers = {**alice, "Idempotency-Key": "one-safe-request"}
        created = client.post("/v1/challenges", headers=key_headers, json={"opponent_username": "bob"})
        assert created.status_code == 201
        challenge_id = created.json()["challenge_id"]
        retried = client.post("/v1/challenges", headers=key_headers, json={"opponent_username": "bob"})
        assert retried.json()["challenge_id"] == challenge_id

        assert client.post(f"/v1/challenges/{challenge_id}/accept", headers=alice).status_code == 403
        accepted = client.post(
            f"/v1/challenges/{challenge_id}/accept",
            headers={**bob, "Idempotency-Key": "accept-once"},
        )
        assert accepted.status_code == 200
        completed = wait_for_challenge(client, challenge_id, alice)
        assert completed["status"] == "completed"
        assert completed["format"] == "best_of_five_plhe"
        assert completed["best_of"] == 5
        assert max(completed["series_score"].values()) == 3
        assert completed["winner_first_score"] == [
            max(completed["series_score"].values()),
            min(completed["series_score"].values()),
        ]
        assert completed["viewer_result"] == (
            "win" if completed["winner_username"] == "alice" else "loss"
        )
        bob_view = client.get(f"/v1/challenges/{challenge_id}", headers=bob).json()
        assert bob_view["viewer_result"] == (
            "win" if completed["winner_username"] == "bob" else "loss"
        )
        assert completed["hands_played"] > 0
        assert completed["run_id"]
        run = client.app.state.db.one("SELECT official,status FROM runs WHERE id=?", (completed["run_id"],))
        assert run == {"official": 0, "status": "completed"}
        assert client.app.state.db.one("SELECT COUNT(*) AS n FROM hands WHERE run_id=?", (completed["run_id"],))["n"] == completed["hands_played"]
        assert client.app.state.db.one("SELECT COUNT(*) AS n FROM leaderboard WHERE run_id=?", (completed["run_id"],))["n"] == 0
        retried_accept = client.post(f"/v1/challenges/{challenge_id}/accept", headers=bob)
        assert retried_accept.status_code == 200
        assert retried_accept.json()["run_id"] == completed["run_id"]
        assert client.app.state.db.one(
            "SELECT COUNT(*) AS n FROM runs WHERE id=?", (completed["run_id"],)
        )["n"] == 1


def test_direct_history_compare_and_nemesis_exclude_official_matchups(tmp_path):
    with auth_client(tmp_path) as client:
        alice = participant(client, "alice")
        participant(client, "bob")
        timestamp = now_iso()
        db = client.app.state.db
        # An official matchup cannot leak into social rivalry history.
        db.execute(
            "INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,completed_at) "
            "VALUES('official_extra','completed',1,'x','x',1,?,?)",
            (timestamp, timestamp),
        )
        db.execute(
            "INSERT INTO matchups VALUES('official_match','official_extra','alice','bob',999,10,1,20,500,400,99)"
        )
        for index in range(4):
            challenge_id = f"direct_{index}"
            db.execute(
                "INSERT INTO rival_challenges(id,challenger_username,challenged_username,status,hand_count,seed,"
                "winner_username,margin_play_chips,created_at,completed_at,updated_at) "
                "VALUES(?, 'alice','bob','completed',200,1,'bob',100,?,?,?)",
                (challenge_id, timestamp, timestamp, timestamp),
            )
        detail = client.get("/v1/rivals/bob", headers=alice).json()
        assert detail["direct_record"] == {"wins": 0, "losses": 4, "draws": 0, "played": 4}
        assert detail["is_nemesis"] is True
        assert len(detail["history"]["items"]) == 4
        first_page = client.get("/v1/rivals/bob/history?limit=2", headers=alice).json()
        assert len(first_page["items"]) == 2
        assert first_page["next_cursor"]
        second_page = client.get(
            f"/v1/rivals/bob/history?limit=2&cursor={first_page['next_cursor']}", headers=alice
        ).json()
        assert len(second_page["items"]) == 2
        assert {item["challenge_id"] for item in first_page["items"]}.isdisjoint(
            item["challenge_id"] for item in second_page["items"]
        )
        compared = client.get("/v1/rivalries/compare?player_a=alice&player_b=bob", headers=alice).json()
        assert compared["direct_record"]["played"] == 4
        assert len(compared["items"]) == 4

        carol = participant(client, "carol")
        other_players = client.get("/v1/rivalries/compare?player_a=alice&player_b=bob", headers=carol).json()
        assert other_players["direct_record"]["played"] == 4
        assert all(item["recap_url"] is None and item["artifacts_url"] is None for item in other_players["items"])
        assert client.get("/v1/challenges/direct_0/recap", headers=carol).status_code == 403


def test_decline_cancel_and_duplicate_open_challenge(tmp_path):
    with auth_client(tmp_path) as client:
        alice = participant(client, "alice")
        bob = participant(client, "bob")
        created = client.post("/v1/challenges", headers=alice, json={"opponent_username": "bob"}).json()
        duplicate = client.post("/v1/challenges", headers=bob, json={"opponent_username": "alice"}).json()
        assert duplicate["challenge_id"] == created["challenge_id"]
        assert client.post(f"/v1/challenges/{created['challenge_id']}/decline", headers=alice).status_code == 403
        declined = client.post(f"/v1/challenges/{created['challenge_id']}/decline", headers=bob)
        assert declined.json()["status"] == "declined"

        second = client.post("/v1/challenges", headers=alice, json={"opponent_username": "bob"}).json()
        assert client.post(f"/v1/challenges/{second['challenge_id']}/cancel", headers=bob).status_code == 403
        cancelled = client.post(f"/v1/challenges/{second['challenge_id']}/cancel", headers=alice)
        assert cancelled.json()["status"] == "cancelled"


def test_concurrent_accept_is_idempotent_and_starts_one_run(tmp_path):
    with auth_client(tmp_path) as client:
        alice = participant(client, "alice")
        bob = participant(client, "bob", "fold")
        created = client.post("/v1/challenges", headers=alice, json={"opponent_username": "bob"}).json()
        challenge_id = created["challenge_id"]

        def accept_once():
            return client.post(
                f"/v1/challenges/{challenge_id}/accept",
                headers={**bob, "Idempotency-Key": "same-accept"},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: accept_once(), range(2)))
        assert {response.status_code for response in responses} == {200}
        completed = wait_for_challenge(client, challenge_id, alice)
        assert completed["status"] == "completed"
        assert client.app.state.db.one(
            "SELECT COUNT(*) AS n FROM runs WHERE id=?", (completed["run_id"],)
        )["n"] == 1
