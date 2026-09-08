"""Create isolated local QA evidence from actual engine hands. Never use live DBs.

PYTHONPATH=server server/.venv/bin/python qa/recap_fixture.py
Run the API with ALPHA_POKER_DATA_DIR=.wrangler/recap-qa, SEED=false,
AUTO_RUN=false, AUTH_REQUIRED=true. QA login: blueriver / local-recap-qa-only.
"""
from pathlib import Path
import json

from alpha_poker.engine import play_hand
from alpha_poker_api.auth import hash_password
from alpha_poker_api.db import Database, now_iso


def main():
    root = Path(__file__).resolve().parents[1] / ".wrangler" / "recap-qa"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "alpha-poker.sqlite3"
    if path.exists():
        raise SystemExit("QA database already exists. Reuse it; this helper never overwrites a database.")
    db = Database(path)
    db.initialize(False)
    timestamp = now_iso()
    for username in ("blueriver", "redace"):
        db.execute("INSERT INTO users(username,password_hash,created_at,updated_at) VALUES(?,?,?,?)", (username, hash_password("local-recap-qa-only"), timestamp, timestamp))
    db.execute("INSERT INTO runs(id,status,official,engine_version,rules_version,seed,requested_at,completed_at) VALUES('run_recap_qa','completed',0,'test','heads-up-v1',1,?,?)", (timestamp, timestamp))
    profits = [20, -60, 0, 200, -40, 840, -80, -100]
    for index, profit in enumerate(profits):
        target = abs(profit) or 20
        def bot(state):
            if state["street"] == "preflop" and "raise" in state["legal_actions"] and state["min_raise_to"] <= target <= state["max_raise_to"]:
                return {"action": "raise", "amount": target}
            return {"action": "check" if "check" in state["legal_actions"] else "call"}
        mapping = [0, 1] if index % 2 == 0 else [1, 0]
        alice_seat = mapping.index(0)
        winning_seat = alice_seat if profit >= 0 else 1 - alice_seat
        holes = [["9s", "9h"], ["9s", "9h"]]
        holes[winning_seat] = ["As", "Kd"]
        if profit == 0:
            holes[1 - winning_seat] = ["Ah", "Kc"]
        hand_id = f"recap_qa_{index + 1}"
        record = play_hand([bot, bot], seed=index, hand_id=hand_id, match_id="match_recap_qa", hand_number=index + 1,
                           starting_stack=2000, small_blind=10, big_blind=20,
                           deal={"holes": holes, "board": ["Ts", "Jd", "Qc", "Kh", "2c"]}).to_dict()
        record.update(players=["blueriver", "redace"], seat_to_bot=mapping, run_id="run_recap_qa")
        assert record["profits"][alice_seat] == profit
        db.execute("INSERT INTO hands VALUES(?,?,?,?,?,?,?,?,?)", (hand_id, "run_recap_qa", index + 1, "blueriver", "redace", "blueriver" if profit > 0 else "redace" if profit < 0 else None, record["pot"], json.dumps(record), ""))
    db.execute("INSERT INTO matchups VALUES('match_recap_qa','run_recap_qa','blueriver','redace',8,1,0,2,3,4,1)")
    db.execute("INSERT INTO rival_challenges(id,challenger_username,challenged_username,status,hand_count,seed,run_id,winner_username,margin_play_chips,created_at,completed_at,updated_at) VALUES('ch_recap_qa','blueriver','redace','completed',8,1,'run_recap_qa','blueriver',?,?,?,?)", (sum(profits), timestamp, timestamp, timestamp))
    print("Isolated QA database ready. Selected hand: /recaps/challenges/ch_recap_qa?hand=recap_qa_6")


if __name__ == "__main__":
    main()
