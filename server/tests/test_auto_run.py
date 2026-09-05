import io
import json
import time
import zipfile

from fastapi.testclient import TestClient

from alpha_poker_api.config import Settings
from alpha_poker_api.main import create_app


def bot_zip(action: str) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(
            "bot.py",
            f"def decide(state):\n    action = '{action}'\n    if action in state['legal_actions']:\n        return {{'action': action}}\n    return {{'action': 'check' if 'check' in state['legal_actions'] else 'call'}}\n",
        )
        archive.writestr(
            "bot.json",
            json.dumps(
                {
                    "api_version": "2026-09-01",
                    "name": "Auto Bot",
                    "language": "python",
                    "entrypoint": "bot.py:decide",
                }
            ),
        )
    return data.getvalue()


def test_accepting_second_bot_automatically_runs_serialized_league(tmp_path):
    settings = Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=False,
        auto_run_on_accept=True,
        auto_run_hand_count=2,
    )
    with TestClient(create_app(settings)) as client:
        for username, action in (("alice", "call"), ("bob", "fold")):
            response = client.post(
                "/v1/submissions",
                data={"username": username, "bot_name": f"{username}-bot"},
                files={"package": ("bot.zip", bot_zip(action), "application/zip")},
            )
            assert response.status_code == 202

        deadline = time.monotonic() + 3
        board = {"entries": []}
        while time.monotonic() < deadline:
            board = client.get("/v1/leaderboard").json()
            if len(board["entries"]) == 2:
                break
            time.sleep(0.01)

        assert len(board["entries"]) == 2
        assert {entry["username"] for entry in board["entries"]} == {"alice", "bob"}
        assert all(entry["hands"] == 2 for entry in board["entries"])
        assert all("elo_rating" in entry for entry in board["entries"])
        assert all(
            entry["matchup_wins"] + entry["matchup_losses"] + entry["matchup_draws"] == 1
            for entry in board["entries"]
        )


def test_one_bot_reports_waiting_instead_of_running_forever(tmp_path):
    settings = Settings(
        tmp_path,
        tmp_path / "db.sqlite3",
        tmp_path / "uploads",
        tmp_path / "artifacts",
        seed_demo_data=False,
        auto_run_on_accept=True,
        auto_run_hand_count=2,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/submissions",
            data={"username": "alice", "bot_name": "alice-bot"},
            files={"package": ("bot.zip", bot_zip("call"), "application/zip")},
        )
        assert response.status_code == 202
        league = client.get("/v1/league").json()
        assert league["queue"]["state"] == "waiting_for_players"
        assert league["queue"]["running"] is False
        assert league["queue"]["active_bot_count"] == 1
        assert league["queue"]["minimum_bot_count"] == 2
        assert "1 more active bot" in league["queue"]["message"]
