from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alpha_poker.engine import HoldemHand

from .db import Database
from .engine_adapter import PortableBot, load_bot


class HouseBot:
    def decide(self, state: dict[str, Any]) -> dict[str, Any]:
        legal = state["legal_actions"]
        return {"action": "check" if "check" in legal else "call" if "call" in legal else "fold"}


@dataclass
class TrainingRuntime:
    session_id: str
    leader: PortableBot | HouseBot
    hand: HoldemHand | None = None
    client_seat: int = 0

    def close(self) -> None:
        close = getattr(self.leader, "close", None)
        if callable(close):
            close()


def build_runtime(db: Database, session: dict[str, Any]) -> TrainingRuntime:
    leader: PortableBot | HouseBot = HouseBot()
    if session.get("leader_submission_id"):
        submission = db.one("SELECT package_path FROM submissions WHERE id=?", (session["leader_submission_id"],))
        if submission:
            leader = load_bot(Path(submission["package_path"]))
    return TrainingRuntime(session["id"], leader)


def start_hand(runtime: TrainingRuntime, session: dict[str, Any]) -> HoldemHand:
    number = int(session["hands_played"]) + 1
    # Consecutive hands share a deal while the participants swap seats.
    pair_index = (number - 1) // 2
    seed_root = int(hashlib.sha256(runtime.session_id.encode()).hexdigest()[:8], 16)
    runtime.client_seat = (number - 1) % 2
    runtime.hand = HoldemHand(
        hand_id=f"{runtime.session_id}_hand_{number}", match_id=runtime.session_id,
        hand_number=number, seed=seed_root + pair_index, dealer=0,
        starting_stack=2000, small_blind=10, big_blind=20, decision_deadline_ms=250,
    )
    return runtime.hand


def public_action_to_engine(message: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    action = message.get("action")
    if action not in state["legal_actions"]:
        raise ValueError("Action is not legal")
    allowed = {"action", "amount", "type", "session_id", "hand_id", "turn_id", "turn_token", "client_action_id"}
    if set(message) - allowed:
        raise ValueError("Action contains unexpected fields")
    if action == "raise":
        amount = message.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ValueError("Raise amount must be an integer")
        if not state["min_raise_to"] <= amount <= state["max_raise_to"]:
            raise ValueError("Raise amount is outside the legal range")
        return {"type": "raise", "to": amount}
    if "amount" in message:
        raise ValueError("Only raise accepts amount")
    return {"type": action}


async def advance_leader(runtime: TrainingRuntime) -> list[dict[str, Any]]:
    hand = runtime.hand
    observed: list[dict[str, Any]] = []
    while hand and not hand.finished and hand.actor != runtime.client_seat:
        state = hand.bot_state(hand.actor)
        try:
            public = await asyncio.wait_for(asyncio.to_thread(runtime.leader.decide, state), timeout=0.25)
            action = public_action_to_engine({"type": "action.submit", **public}, state)
        except Exception as exc:
            hand.events.append({
                "type": "bot_error", "seat": hand.actor, "street": hand.street,
                "error": f"{type(exc).__name__}: {exc}", "fallback": "forfeit",
                "elapsed_ms_upper_bound": 250,
            })
            hand.forfeit(hand.actor)
            observed.append({"seat": 1 - runtime.client_seat, "action": "forfeit"})
            break
        hand.act(action)
        observed.append({"seat": 1 - runtime.client_seat, "action": public["action"], "amount": public.get("amount")})
    return observed


def persist_completed_hand(db: Database, runtime: TrainingRuntime) -> dict[str, Any]:
    hand = runtime.hand
    if not hand or not hand.finished:
        raise ValueError("training hand is not complete")
    result = hand.result()
    session = db.one("SELECT * FROM training_sessions WHERE id=?", (runtime.session_id,))
    players = [None, None]
    players[runtime.client_seat] = session["username"]
    players[1 - runtime.client_seat] = session["leader_username"]
    history = result.to_dict()
    history["players"] = players
    history["client_seat"] = runtime.client_seat
    history["client_profit"] = result.profits[runtime.client_seat]
    db.execute(
        "INSERT OR REPLACE INTO training_hands VALUES(?,?,?,?,?,?)",
        (runtime.session_id, hand.hand_number, hand.hand_id, runtime.client_seat,
         result.profits[runtime.client_seat], json.dumps(history)),
    )
    db.execute("UPDATE training_sessions SET hands_played=hands_played+1 WHERE id=?", (runtime.session_id,))
    return history
