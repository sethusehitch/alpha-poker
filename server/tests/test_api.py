import io
import json
import zipfile

from alpha_poker_api.jobs import run_official_league


def bot_zip(valid=True):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("bot.py", "def decide(state):\n    return {'action': 'call'}\n")
        if valid:
            archive.writestr("bot.json", json.dumps({
                "api_version": "2026-09-01", "name": "Test Bot",
                "language": "python", "entrypoint": "bot.py:decide",
            }))
    return data.getvalue()


def broken_python_zip():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("bot.py", "def decide(:\n")
        archive.writestr("bot.json", json.dumps({
            "name": "Broken", "api_version": "2026-09-01",
            "language": "python", "entrypoint": "bot.py:decide",
        }))
    return data.getvalue()


def test_public_league_leaderboard_and_results(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/health").json() == {"status": "ok"}
    league = client.get("/v1/league").json()
    assert league["play_money_only"] is True
    board = client.get("/v1/leaderboard").json()
    assert board["entries"][0]["rank"] == 1
    assert board["entries"][0]["elo_rating"] == 1264
    assert board["entries"][0]["matchup_wins"] == 4
    assert board["entries"][0]["matchup_losses"] == 0
    assert "confidence_95" not in board["entries"][0]
    assert board["top_entries"] == board["entries"][:5]
    assert board["viewer_entry"] is None
    assert client.get("/v1/runs/run_demo").json()["reproducibility"]["deterministic"] is True
    assert len(client.get("/v1/runs/run_demo/matchups").json()["matchups"]) == 3


def test_leaderboard_exposes_top_five_and_authenticated_viewer(client):
    registration = client.post(
        "/v1/auth/register", json={"username": "sixthplace", "password": "correct horse"}
    )
    headers = {"Authorization": f"Bearer {registration.json()['token']}"}
    client.app.state.db.execute(
        "INSERT INTO leaderboard(run_id,rank,username,bot_name,bb_per_100,ci_low,ci_high,hands,"
        "submission_id,elo_rating,matchup_wins,matchup_losses,matchup_draws) "
        "VALUES('run_demo',6,'sixthplace','SixthBot',-9,-10,-8,100,NULL,1100,0,5,0)"
    )

    board = client.get("/v1/leaderboard", headers=headers).json()
    assert [entry["rank"] for entry in board["top_entries"]] == [1, 2, 3, 4, 5]
    assert board["viewer_entry"]["username"] == "sixthplace"
    assert board["viewer_entry"]["rank"] == 6

    public = client.get("/v1/leaderboard").json()
    assert public["viewer_entry"] is None


def test_public_standings_ignore_newer_nonofficial_runs(client):
    client.app.state.db.execute(
        "INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,completed_at,hand_count_per_pairing) "
        "VALUES('run_archived','completed',0,'prototype-0.1','heads-up-v1',7,'2099-01-01T00:00:00Z','2099-01-01T00:01:00Z',2)"
    )

    assert client.get("/v1/league").json()["current_run"]["id"] == "run_demo"
    assert client.get("/v1/leaderboard").json()["run_id"] == "run_demo"
    assert client.get("/v1/matchups").json()["run_id"] == "run_demo"
    assert {run["id"] for run in client.get("/v1/runs").json()["runs"]} == {"run_demo"}


def test_hand_and_artifact_downloads(client):
    hand = client.get("/v1/hands/hand_demo_1")
    assert hand.json()["winner"] == "maya"
    assert 'variant = "NT"' in client.get("/v1/hands/hand_demo_1/phh").text
    artifact = client.get("/v1/runs/run_demo/artifacts")
    assert artifact.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        assert set(archive.namelist()) == {"result.txt", "summary.json", "hands.phhs", "hands.jsonl"}
        summary = json.loads(archive.read("summary.json"))
        assert summary["methodology"]["rating_period"] == "once per completed best-of-five series"
        assert "RiverRat" in summary["overview"]
    public_summary = client.get("/v1/runs/run_demo/summary")
    assert public_summary.status_code == 200
    assert "RiverRat" in public_summary.json()["overview"]


def test_competition_phh_contains_pot_limit_extension_and_action_sequence(client):
    for username in ("maya", "theo"):
        upload = client.post(
            "/v1/submissions",
            data={"username": username, "bot_name": f"{username}-bot"},
            files={"package": ("bot.zip", bot_zip(), "application/zip")},
        )
        assert upload.status_code == 202
    response = client.post("/v1/admin/runs", json={"seed": 1717})
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    phh = client.app.state.db.one(
        "SELECT phh FROM hands WHERE run_id=? ORDER BY hand_number LIMIT 1", (run_id,)
    )["phh"]
    assert '# Alpha Poker PHH extension: PT = pot-limit Texas hold\'em' in phh
    assert 'variant = "PT"' in phh
    assert "actions = [" in phh
    assert "d dh p" in phh


def test_upload_activates_valid_bot_and_preserves_it_after_rejection(client):
    first = client.post(
        "/v1/submissions", data={"username": "tester", "bot_name": "GoodBot"},
        files={"package": ("alpha-poker-submission.zip", bot_zip(), "application/zip")},
        headers={"Idempotency-Key": "first"},
    )
    assert first.status_code == 202
    first_id = first.json()["submission_id"]
    assert client.get(f"/v1/submissions/{first_id}").json()["status"] == "accepted"
    assert client.get("/v1/submissions/current?username=tester").json()["bot_name"] == "GoodBot"
    validation_log = client.get(f"/v1/submissions/{first_id}/logs").text
    assert "Isolated smoke validation complete" in validation_log
    assert "unavailable" not in validation_log

    rejected = client.post(
        "/v1/submissions", data={"username": "tester", "bot_name": "BadBot"},
        files={"package": ("broken.zip", bot_zip(False), "application/zip")},
    )
    rejected_id = rejected.json()["submission_id"]
    assert client.get(f"/v1/submissions/{rejected_id}").json()["status"] == "rejected"
    assert client.get("/v1/submissions/current", headers={"X-Alpha-Username": "tester"}).json()["bot_name"] == "GoodBot"


def test_validation_rejects_bot_that_cannot_import(client):
    response = client.post(
        "/v1/submissions", data={"username": "tester", "bot_name": "Broken"},
        files={"package": ("broken.zip", broken_python_zip(), "application/zip")},
    )
    result = client.get(f"/v1/submissions/{response.json()['submission_id']}").json()
    assert result["status"] == "rejected"
    assert "SyntaxError" in result["error"]


def test_validation_rejects_manifest_outside_the_public_contract(client):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("bot.py", "def decide(state):\n    return {'action': 'call'}\n")
        archive.writestr("bot.json", json.dumps({"name": "Incomplete", "api_version": "2026-09-01"}))
    response = client.post(
        "/v1/submissions", data={"username": "tester", "bot_name": "Incomplete"},
        files={"package": ("bot.zip", data.getvalue(), "application/zip")},
    )
    result = client.get(f"/v1/submissions/{response.json()['submission_id']}").json()
    assert result["status"] == "rejected"
    assert result["error"] == "language must be python"


def test_upload_idempotency(client):
    kwargs = dict(
        data={"username": "tester", "bot_name": "Bot"},
        files={"package": ("bot.zip", bot_zip(), "application/zip")},
        headers={"Idempotency-Key": "same-request"},
    )
    one = client.post("/v1/submissions", **kwargs)
    two = client.post("/v1/submissions", **kwargs)
    assert one.json()["submission_id"] == two.json()["submission_id"]

    other_user = client.post(
        "/v1/submissions",
        data={"username": "someone-else", "bot_name": "Bot"},
        files={"package": ("bot.zip", bot_zip(), "application/zip")},
        headers={"Idempotency-Key": "same-request"},
    )
    assert other_user.json()["submission_id"] != one.json()["submission_id"]


def test_cli_style_upload_defaults_to_local_username(client):
    response = client.post(
        "/v1/submissions", data={"bot_name": "Starter"},
        files={"package": ("alpha-poker-submission.zip", bot_zip(), "application/zip")},
    )
    assert response.status_code == 202
    assert client.get("/v1/submissions/current?username=local").json()["bot_name"] == "Starter"


def test_training_freezes_current_leader_submission(client):
    uploaded = client.post(
        "/v1/submissions", data={"username": "maya", "bot_name": "Leader One"},
        files={"package": ("leader.zip", bot_zip(), "application/zip")},
    ).json()
    session = client.post("/v1/training/sessions", json={"username": "challenger", "hand_limit": 2}).json()
    client.post(
        "/v1/submissions", data={"username": "maya", "bot_name": "Leader Two"},
        files={"package": ("leader.zip", bot_zip(), "application/zip")},
    )
    frozen = client.app.state.db.one("SELECT leader_submission_id FROM training_sessions WHERE id=?", (session["session_id"],))
    assert frozen["leader_submission_id"] == uploaded["submission_id"]


def test_training_ignores_nonofficial_qa_leaderboards(client):
    db = client.app.state.db
    db.execute(
        "INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,completed_at,hand_count_per_pairing) "
        "VALUES('run_qa_latest','completed',0,'prototype-0.1','heads-up-v1',1,'9999-01-01T00:00:00Z','9999-01-01T00:00:00Z',2)"
    )
    db.execute(
        "INSERT INTO leaderboard(run_id,rank,username,bot_name,bb_per_100,ci_low,ci_high,hands,submission_id,elo_rating,matchup_wins,matchup_losses,matchup_draws) "
        "VALUES('run_qa_latest',1,'qa-player','Temporary QA Bot',1,0,2,2,NULL,1200,1,0,0)"
    )

    session = client.post(
        "/v1/training/sessions",
        json={"username": "challenger", "hand_limit": 1},
    ).json()
    frozen = db.one(
        "SELECT leader_username,leader_submission_id FROM training_sessions WHERE id=?",
        (session["session_id"],),
    )

    assert frozen["leader_username"] == "maya"
    assert frozen["leader_submission_id"] is None


def test_training_websocket_url_respects_https_proxy(client):
    session = client.post(
        "/v1/training/sessions",
        json={"username": "challenger", "hand_limit": 1},
        headers={"X-Forwarded-Proto": "https", "Host": "poker.example"},
    ).json()
    assert session["websocket_url"].startswith("wss://poker.example/v1/training/ws?")


def test_training_session_creation_never_waits_for_an_official_run_lock(client):
    class LockMustNotBeUsed:
        def __enter__(self):
            raise AssertionError("training creation must not acquire the league execution lock")

        def __exit__(self, *_args):
            return False

    client.app.state.league_execution_lock = LockMustNotBeUsed()
    response = client.post(
        "/v1/training/sessions",
        json={"username": "challenger", "hand_limit": 2},
    )
    assert response.status_code == 201
    assert response.json()["session_id"].startswith("trn_")


def test_training_rejects_an_unsupported_client_contract(client):
    response = client.post(
        "/v1/training/sessions",
        json={"username": "challenger", "client_schema_version": "old-version"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_invalid"


def test_errors_have_stable_shape(client):
    response = client.get("/v1/hands/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "hand_not_found"


def test_can_queue_official_run(client):
    response = client.post("/v1/admin/runs", json={"hand_count_per_pairing": 2000, "seed": 42})
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    assert client.get(f"/v1/runs/{run_id}").json()["seed"] == 42


def test_official_run_accepts_legacy_hand_count_without_using_it_as_a_cap(client):
    response = client.post("/v1/admin/runs", json={"hand_count_per_pairing": 3, "seed": 42})
    assert response.status_code == 202
    assert response.json()["format"] == "best_of_five_plhe"


def test_official_run_uses_active_uploaded_bots(client):
    for username in ("left", "right"):
        response = client.post(
            "/v1/submissions", data={"username": username, "bot_name": f"{username} bot"},
            files={"package": ("bot.zip", bot_zip(), "application/zip")},
        )
        assert client.get(f"/v1/submissions/{response.json()['submission_id']}").json()["status"] == "accepted"
    response = client.post("/v1/admin/runs", json={"hand_count_per_pairing": 2, "seed": 101})
    run_id = response.json()["run_id"]
    assert client.get(f"/v1/runs/{run_id}").json()["status"] == "completed"
    result = client.get(f"/v1/runs/{run_id}/matchups").json()
    assert 3 <= sum(result["matchups"][0]["series_score"]) <= 5
    assert result["matchups"][0]["hands"] > 0
    hand_id = client.app.state.db.one("SELECT id FROM hands WHERE run_id=? LIMIT 1", (run_id,))["id"]
    phh = client.get(f"/v1/hands/{hand_id}/phh").text
    assert "blinds_or_straddles = [50, 100]" in phh
    assert "starting_stacks = [10000, 10000]" in phh
    board = client.get("/v1/leaderboard").json()
    assert board["run_id"] == run_id
    assert {entry["username"] for entry in board["entries"]} == {"left", "right"}
    assert all("elo_rating" in entry for entry in board["entries"])
    assert {entry["matchup_wins"] + entry["matchup_losses"] + entry["matchup_draws"] for entry in board["entries"]} == {1}
    detail = client.get(f"/v1/runs/{run_id}").json()
    assert detail["started_at"]
    assert detail["heartbeat_at"]
    assert detail["progress"]["matchups_completed"] == 1
    assert detail["progress"]["matchups_total"] == 1
    history = client.app.state.db.all(
        "SELECT username,rating_before,rating_after,k_factor FROM elo_history WHERE run_id=? ORDER BY username",
        (run_id,),
    )
    assert len(history) == 2
    assert {row["k_factor"] for row in history} == {40}
    assert {row["rating_before"] for row in history} == {1200}
    run_official_league(client.app.state.db, run_id, 2)
    assert client.app.state.db.one("SELECT COUNT(*) AS n FROM elo_history WHERE run_id=?", (run_id,))["n"] == 2


def test_replacing_a_bot_keeps_the_players_elo_and_updates_once_per_series(client):
    submission_ids = {}
    for username in ("left", "right"):
        response = client.post(
            "/v1/submissions", data={"username": username, "bot_name": f"{username} bot"},
            files={"package": ("bot.zip", bot_zip(), "application/zip")},
        )
        submission_ids[username] = response.json()["submission_id"]
    first_run = client.post("/v1/admin/runs", json={"seed": 717}).json()["run_id"]
    first_after = {
        row["username"]: row["rating_after"]
        for row in client.app.state.db.all("SELECT username,rating_after FROM elo_history WHERE run_id=?", (first_run,))
    }
    replacement = client.post(
        "/v1/submissions", data={"username": "left", "bot_name": "left replacement"},
        files={"package": ("bot.zip", bot_zip(), "application/zip")},
    ).json()["submission_id"]
    assert replacement != submission_ids["left"]
    second_run = client.post("/v1/admin/runs", json={"seed": 718}).json()["run_id"]
    second_history = client.app.state.db.all(
        "SELECT username,submission_id,rating_before FROM elo_history WHERE run_id=? ORDER BY username",
        (second_run,),
    )
    assert len(second_history) == 2
    assert {row["username"]: row["rating_before"] for row in second_history} == first_after
    assert next(row for row in second_history if row["username"] == "left")["submission_id"] == replacement


def test_official_run_and_leaderboard_support_twenty_active_bots(client):
    usernames = {f"player-{index:02d}" for index in range(1, 21)}
    for username in sorted(usernames):
        response = client.post(
            "/v1/submissions",
            data={"username": username, "bot_name": f"Bot {username}"},
            files={"package": ("bot.zip", bot_zip(), "application/zip")},
        )
        assert response.status_code == 202

    run = client.post(
        "/v1/admin/runs", json={"hand_count_per_pairing": 2, "seed": 2020}
    )
    assert run.status_code == 202

    board = client.get("/v1/leaderboard").json()
    assert board["run_id"] == run.json()["run_id"]
    assert len(board["entries"]) == 20
    assert [entry["rank"] for entry in board["entries"]] == list(range(1, 21))
    assert {entry["username"] for entry in board["entries"]} == usernames
    assert all(entry["hands"] > 0 for entry in board["entries"])
    assert {
        entry["matchup_wins"] + entry["matchup_losses"] + entry["matchup_draws"]
        for entry in board["entries"]
    } == {19}
    assert all(isinstance(entry["elo_rating"], int) for entry in board["entries"])


def test_training_uses_the_exact_submission_that_earned_first_place(client):
    uploaded = {}
    for username in ("aaa", "zzz"):
        response = client.post(
            "/v1/submissions", data={"username": username, "bot_name": f"{username} bot"},
            files={"package": ("bot.zip", bot_zip(), "application/zip")},
        )
        uploaded[username] = response.json()["submission_id"]
    run = client.post("/v1/admin/runs", json={"hand_count_per_pairing": 2, "seed": 501}).json()
    assert client.get(f"/v1/runs/{run['run_id']}").json()["status"] == "completed"
    winner = client.get("/v1/leaderboard").json()["entries"][0]["username"]

    client.post(
        "/v1/submissions", data={"username": winner, "bot_name": "Replacement"},
        files={"package": ("bot.zip", bot_zip(), "application/zip")},
    )
    session = client.post("/v1/training/sessions", json={"username": "challenger", "hand_limit": 2}).json()
    frozen = client.app.state.db.one(
        "SELECT leader_submission_id FROM training_sessions WHERE id=?", (session["session_id"],),
    )
    assert frozen["leader_submission_id"] == uploaded[winner]
