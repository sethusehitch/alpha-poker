import json

import pytest
from fastapi.testclient import TestClient

from alpha_poker.engine import play_hand
from alpha_poker_api.config import Settings
from alpha_poker_api.db import now_iso
from alpha_poker_api.main import create_app
from alpha_poker_api.recaps import normalize_hand, select_highlights


MATCH = {"id": "match_1", "run_id": "run_1", "player_a": "alice", "player_b": "bob", "hands": 6}


def hand_record(kind="showdown", mirror=False):
    def bot(state):
        if kind == "fold":
            return {"action": "fold"}
        if kind == "all_in" and "all_in" in state["legal_actions"]:
            return {"action": "all_in"}
        return {"action": "check" if "check" in state["legal_actions"] else "call"}
    history = play_hand([bot, bot], seed=1, hand_id="hand_1", match_id="match_1",
                        starting_stack=2000, small_blind=10, big_blind=20,
                        deal={"holes": [["As", "Kd"], ["9s", "9h"]], "board": ["Ts", "Jd", "Qc", "Kh", "2c"]}).to_dict()
    history.update(players=["alice", "bob"], seat_to_bot=[1, 0] if mirror else [0, 1])
    return history


def normalized(record):
    return normalize_hand(record, {"id": "hand_1", "hand_number": 1, "pot": record.get("pot", 0)}, MATCH, "alice")


def series(profits):
    return [{"hand_id": f"h{i:03}", "hand_number": i + 1, "profit_a": p, "pot": abs(p) * 2 if p is not None else 200,
             "big_blind": 20, "winners": ["alice", "bob"] if p == 0 else ["alice" if p and p > 0 else "bob"],
             "reason": "showdown"} for i, p in enumerate(profits)]


def labels(hands):
    return {label for h in hands for label in h["labels"]}


def test_selector_is_deterministic_chronological_deduplicated_and_bounded():
    hands = series([20, -60, 0, 100, -20, -60, 160, -20])
    selected = select_highlights(hands, complete=True)
    assert selected == select_highlights(list(reversed(hands)), complete=True)
    assert len(selected) == len({h["hand_id"] for h in selected}) == 5
    assert [h["hand_number"] for h in selected] == sorted(h["hand_number"] for h in selected)
    assert {"Opening momentum", "First lead change", "Biggest comeback", "Largest single-hand swing"} <= labels(selected)


def test_ties_and_short_matches_do_not_invent_momentum():
    assert select_highlights([], complete=True) == []
    for count in (1, 2, 4):
        result = select_highlights(series([0] * count), complete=True)
        assert len(result) == count
        assert labels(result) == {"Split pot"}
    one = select_highlights(series([100]), complete=True)
    assert len(one) == 1
    assert set(one[0]["labels"]) == {"Largest single-hand swing", "Opening momentum", "Final scoring hand"}


def test_equal_swings_choose_earliest_and_final_draw_is_explicit():
    result = select_highlights(series([100, -100, 100, -100]), complete=True)
    swing = next(h for h in result if "Largest single-hand swing" in h["labels"])
    assert swing["hand_number"] == 1
    assert "Draw sealed" in result[-1]["labels"]
    assert "Final lead change" not in labels(result)


def test_partial_or_unknown_profit_history_never_claims_a_match_arc():
    for complete, profits in ((False, [100, -200, 300]), (True, [100, None, 300])):
        result = select_highlights(series(profits), complete=complete)
        assert not labels(result) & {"Opening momentum", "First lead change", "Biggest comeback", "Final lead change", "Largest single-hand swing"}
        assert "Largest retained swing" in labels(result)


@pytest.mark.parametrize("kind", ["showdown", "all_in"])
def test_showdown_rank_seat_mapping_and_chip_conservation(kind):
    record = hand_record(kind, mirror=True)
    result = normalized(record)
    assert result["outcome"] == "bob wins with ace-high straight"
    assert [p["username"] for p in result["players"]] == ["bob", "alice"]
    assert result["profit_a"] < 0
    assert sum(p["profit"] for p in result["players"]) == 0
    assert sum(result["steps"][-1]["stacks"]) == 4000
    assert result["steps"][0]["hole_cards"] == [[], ["9s", "9h"]]
    assert result["steps"][-1]["hole_cards"] == [["As", "Kd"], ["9s", "9h"]]
    assert result["pot"] == (4000 if kind == "all_in" else 40)
    if kind == "all_in":
        assert any("all in" in step["summary"] for step in result["steps"])
        assert any(step["stacks"] == [0, 0] for step in result["steps"][:-1])


def test_fold_never_leaks_opponent_cards_or_undealt_board():
    result = normalized(hand_record("fold"))
    assert result["outcome"] == "bob wins after a fold"
    assert result["board"] == []
    assert result["players"][1]["hole_cards"] == []
    assert all(step["hole_cards"][1] == [] for step in result["steps"])
    assert result["players"][0]["profit"] == -10
    assert result["pot"] == 30  # gross pot is not the +10 net win


def test_missing_fields_and_forfeit_are_honest():
    result = normalized({"players": ["alice", "bob"], "events": [], "pot": 0})
    assert result["profit_a"] is None
    assert result["outcome"] == "Result details unavailable"
    assert result["steps"][-1]["stacks"] == [None, None]
    assert result["steps"][-1]["hole_cards"] == [[], []]
    record = hand_record("fold")
    record["events"][-1]["reason"] = "bot_forfeit"
    record["events"].insert(-1, {"type": "bot_error", "error": "private bot details"})
    result = normalized(record)
    assert result["outcome"] == "bob wins by bot forfeit"
    assert "private bot details" not in json.dumps(result)


def test_missing_action_payment_does_not_invent_intermediate_stacks():
    record = hand_record()
    del record["events"][2]["amount"]
    del record["events"][2]["pot_after"]
    result = normalized(record)
    assert result["steps"][2]["stacks"][0] is None
    assert result["steps"][2]["pot"] is None
    assert result["steps"][-1]["stacks"] == record["final_stacks"]


def seed(db, *, official=False):
    timestamp = now_iso()
    db.execute("INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,completed_at) VALUES('run_1','completed',?,'test','test',1,?,?)", (int(official), timestamp, timestamp))
    db.execute("INSERT INTO matchups VALUES('match_1','run_1','alice','bob',6,1,0,2,4,2,0)")
    if not official:
        db.execute("INSERT INTO rival_challenges(id,challenger_username,challenged_username,status,hand_count,seed,run_id,created_at,completed_at,updated_at) VALUES('ch_1','alice','bob','completed',6,1,'run_1',?,?,?)", (timestamp, timestamp, timestamp))
    for number in range(1, 7):
        record = hand_record("fold" if number % 2 else "showdown", mirror=bool(number % 2))
        record.update(hand_id=f"hand_{number}", hand_number=number)
        db.execute("INSERT INTO hands VALUES(?,?,?,?,?,?,?,?,?)", (f"hand_{number}", "run_1", number, "alice", "bob", None, record["pot"], json.dumps(record), ""))


@pytest.fixture
def recap_client(tmp_path):
    with TestClient(create_app(Settings(tmp_path, tmp_path / "db", tmp_path / "uploads", tmp_path / "artifacts", seed_demo_data=False, auth_required=True))) as client:
        headers = {}
        for user in ("alice", "bob", "carol"):
            data = client.post("/v1/auth/register", json={"username": user, "password": "correct horse"}).json()
            headers[user] = {"Authorization": f"Bearer {data['token']}"}
        yield client, headers


def test_direct_authorization_scope_discovery_and_retention(recap_client):
    client, headers = recap_client
    db = client.app.state.db
    seed(db)
    endpoint = "/v1/challenges/ch_1/recap"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers=headers["carol"]).status_code == 403
    response = client.get(endpoint, headers=headers["alice"])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    data = response.json()
    assert data["playback_url"] == "/recaps/challenges/ch_1"
    assert data["complete_history"] and len(data["highlights"]) == 5
    assert data["best_hands"][0]["hand_id"] == data["highlights"][0]["hand_id"]
    assert client.get("/v1/challenges/ch_1", headers=headers["alice"]).json()["playback_url"] == data["playback_url"]
    assert client.get("/v1/challenges?status=finished", headers=headers["alice"]).json()["items"][0]["playback_url"] == data["playback_url"]
    path = "/v1/runs/run_1/matchups/match_1/recap"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers["carol"]).status_code == 403
    assert client.get(path, headers=headers["bob"]).json()["source"] == "direct_challenge"
    assert client.get(path, headers=headers["bob"]).json()["challenge"]["challenge_id"] == "ch_1"
    assert client.get("/v1/challenges/no_such/recap", headers=headers["alice"]).status_code == 404
    db.execute("UPDATE rival_challenges SET status='running' WHERE id='ch_1'")
    assert client.get(endpoint, headers=headers["alice"]).status_code == 409
    db.execute("UPDATE rival_challenges SET status='completed' WHERE id='ch_1'")
    db.execute("DELETE FROM hands WHERE run_id='run_1'")
    data = client.get(endpoint, headers=headers["alice"]).json()
    assert data["highlights"] == [] and not data["complete_history"]


def test_round_robin_never_mixes_pairings_or_runs(recap_client):
    client, headers = recap_client
    db = client.app.state.db
    seed(db, official=True)
    db.execute("INSERT INTO matchups VALUES('match_other','run_1','alice','carol',1,1,0,2,1,0,0)")
    record = hand_record()
    record.update(hand_id="other", match_id="match_other", players=["alice", "carol"])
    db.execute("INSERT INTO hands VALUES('other','run_1',7,'alice','carol','alice',999999,?, '')", (json.dumps(record),))
    # A same-pair record carrying another match ID is also excluded.
    record.update(match_id="not_this_match", players=["alice", "bob"])
    db.execute("INSERT INTO hands VALUES('wrong_match','run_1',8,'alice','bob','alice',999999,?, '')", (json.dumps(record),))
    data = client.get("/v1/runs/run_1/matchups/match_1/recap").json()
    assert data["source"] == "round_robin" and data["retained_hands"] == 6
    assert all(h["hand_id"] not in {"other", "wrong_match"} for h in data["highlights"])
    assert all(not p["is_viewer"] for h in data["highlights"] for p in h["players"])
    assert client.get("/v1/runs/run_other/matchups/match_1/recap").status_code == 404
    assert client.get("/v1/runs/run_1/matchups/missing/recap").status_code == 404
    db.execute("UPDATE runs SET status='running' WHERE id='run_1'")
    assert client.get("/v1/runs/run_1/matchups/match_1/recap").status_code == 409
