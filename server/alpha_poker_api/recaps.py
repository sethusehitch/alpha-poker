"""Versioned, deterministic completed-match highlights. No extra persistence.

Amounts called a swing are one player's net hand profit, not the gross pot.
Lead/comeback labels require a complete, known-profit match. Mirrored seats are
mapped back to matchup players before computing the cumulative score.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from alpha_poker.evaluator import describe, evaluate
from .recap_chips import street_wagers
from .recap_equity import showdown_equity


def integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def cards(value: Any) -> list[str]:
    return [c for c in value if isinstance(c, str) and len(c) == 2 and c[0] in "23456789TJQKA" and c[1] in "cdhs"] if isinstance(value, list) else []


def pair(value: Any) -> list[int | None]:
    return [integer(value[i]) if isinstance(value, list) and len(value) > i else None for i in range(2)]


def _category(hole: list[str], board: list[str]) -> str | None:
    try:
        rank = evaluate(hole + board)
    except ValueError:
        return None
    label = describe(rank).replace("_", " ")
    if rank[0] in (0, 4, 5, 8):
        high = {14: "ace", 13: "king", 12: "queen", 11: "jack"}.get(rank[1], str(rank[1]))
        return f"{high}-high {label}" if rank[0] != 0 else f"{high} high"
    return label


def normalize_hand(record: dict, row: dict, matchup: dict, viewer: str | None, *, include_steps: bool = True, equity_cache: dict | None = None) -> dict:
    names = [matchup["player_a"], matchup["player_b"]]
    record_names = record.get("players")
    # Legacy records may list the matchup pair in reverse order.
    if not isinstance(record_names, list) or len(record_names) != 2 or set(record_names) != set(names):
        record_names = names
    mapping = record.get("seat_to_bot", [0, 1])
    if mapping not in ([0, 1], [1, 0]):
        mapping = [0, 1]
    seat_names = [record_names[index] for index in mapping]
    starts, finals, profits = (pair(record.get(key)) for key in ("starting_stacks", "final_stacks", "profits"))
    bot_profits = pair(record.get("bot_profits"))
    for seat in range(2):
        if profits[seat] is None:
            profits[seat] = bot_profits[mapping[seat]]
        if profits[seat] is None and starts[seat] is not None and finals[seat] is not None:
            profits[seat] = finals[seat] - starts[seat]
        if finals[seat] is None and starts[seat] is not None and profits[seat] is not None:
            finals[seat] = starts[seat] + profits[seat]
    events = record.get("events")
    events = [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    reason = result.get("reason")
    winners = result.get("winners", record.get("winners"))
    winners = [s for s in winners if type(s) is int and s in (0, 1)] if isinstance(winners, list) else []
    if not winners and row.get("winner") in seat_names:
        winners = [seat_names.index(row["winner"])]
    if not winners and profits == [0, 0]:
        winners = [0, 1]
    pot = integer(record.get("pot"))
    if pot is None:
        pot = integer(row.get("pot"))
    known_profit = all(p is not None for p in profits) and sum(profits) == 0
    metadata = {
        "hand_id": row["id"], "hand_number": integer(record.get("hand_number")) or row["hand_number"],
        "pot": pot, "winners": [seat_names[s] for s in winners],
        "reason": reason if reason in ("showdown", "fold", "bot_forfeit") else None,
        "profit_a": profits[seat_names.index(names[0])] if known_profit else None,
        "big_blind": integer((record.get("blinds") or {}).get("big")) if isinstance(record.get("blinds"), dict) else None,
    }
    if not include_steps:
        return metadata
    holes = record.get("hole_cards", [])
    holes = [cards(holes[s]) if isinstance(holes, list) and len(holes) > s else [] for s in range(2)]
    board = cards(record.get("board"))
    revealed: set[int] = set()
    showdown_cards: dict[int, list[str]] = {}
    for event in events:
        if event.get("type") == "showdown":
            for shown in event.get("hands", []) if isinstance(event.get("hands"), list) else []:
                if isinstance(shown, dict) and type(shown.get("seat")) is int and shown["seat"] in (0, 1):
                    revealed.add(shown["seat"])
                    showdown_cards[shown["seat"]] = cards(shown.get("hole_cards"))
    for seat, shown in showdown_cards.items():
        if shown:
            holes[seat] = shown
    categories = {seat: _category(holes[seat], board) for seat in revealed}
    winner_names = [seat_names[s] for s in winners]
    if len(winners) == 2:
        outcome = "Split pot"
    elif winners:
        name = winner_names[0]
        category = categories.get(winners[0])
        if reason == "showdown" and category:
            outcome = f"{name} wins with {category}"
        elif reason == "fold":
            outcome = f"{name} wins after a fold"
        elif reason == "bot_forfeit":
            outcome = f"{name} wins by bot forfeit"
        else:
            outcome = f"{name} wins the hand"
    else:
        outcome = "Result details unavailable"
    players = [{"username": seat_names[s], "seat": s, "is_viewer": seat_names[s] == viewer,
                "starting_stack": starts[s], "final_stack": finals[s], "profit": profits[s],
                "hole_cards": holes[s],
                "cards_revealed": s in revealed, "category": categories.get(s)} for s in range(2)]
    steps: list[dict] = []
    step_board: list[str] = []
    stacks = list(starts)
    step_pot: int | None = 0 if all(n is not None for n in starts) else None
    # Completed recaps are retrospective: show all retained cards from the deal.
    visible = [list(hand) for hand in holes]
    for event in events:
        kind, seat = event.get("type"), event.get("seat")
        seat = seat if type(seat) is int and seat in (0, 1) else None
        name = seat_names[seat] if seat is not None else "Player"
        street = event.get("street") if event.get("street") in ("preflop", "flop", "turn", "river", "showdown") else "preflop"
        amount = integer(event.get("amount"))
        # `amount` is the recorded payment, whereas `to` is a street total.
        # Never infer a flight from a raise target, stack change, or final pot.
        pot_before = step_pot
        actor_seat, action_kind, committed = None, None, None
        if kind in ("small_blind", "big_blind", "action"):
            actor_seat = seat
            action_kind = kind if kind != "action" else event.get("action")
            if action_kind not in {"small_blind", "big_blind", "fold", "check", "call", "bet", "raise", "all_in"}:
                action_kind = None
            committed = 0 if action_kind in {"fold", "check"} else amount if amount is not None and amount >= 0 else None
            amount = committed
            if seat is not None and amount is not None and amount >= 0:
                if stacks[seat] is not None:
                    stacks[seat] -= amount
                if step_pot is not None:
                    step_pot += amount
            elif seat is not None and (kind != "action" or event.get("action") in {"call", "bet", "raise", "all_in"}):
                stacks[seat], step_pot = None, None
            if integer(event.get("pot_after")) is not None:
                step_pot = event["pot_after"]
            action = {"fold": "folds", "check": "checks", "call": "calls", "bet": "bets", "raise": "raises", "all_in": "goes all in"}.get(event.get("action"), "acts")
            if kind != "action":
                action = "posts the " + kind.replace("_", " ")
            copy = f"{name} {action}" + (f" ({amount:,} chips paid)" if amount else "")
            action_label = f"{name} {action}"
            if amount:
                # An incremental raise payment is not a raise-to amount.
                action_label += f" · {amount:,} paid" if action_kind in {"raise", "all_in"} else f" {amount:,}"
        elif kind == "board":
            step_board = cards(event.get("cards"))
            copy = f"{street.capitalize()} dealt"
        elif kind == "showdown":
            street, copy = "showdown", "Players reveal their hands"
        elif kind == "forfeit":
            copy = f"{name} forfeits after a bot error"
        elif kind == "result":
            stacks, step_pot = list(finals), pot
            street, copy = "result", outcome
        else:
            # Do not echo bot error strings or arbitrary legacy event text.
            continue
        steps.append({"street": street, "summary": copy, "board": list(step_board),
                      "actor_seat": actor_seat, "action_kind": action_kind, "committed_amount": committed,
                      "pot_before": pot_before, "action_label": action_label if kind in ("small_blind", "big_blind", "action") else copy,
                      "pot": step_pot, "stacks": list(stacks), "hole_cards": [list(c) for c in visible]})
    # Every replay ends at the retained final state, including legacy records.
    final = {"street": "result", "summary": outcome, "board": board, "pot": pot,
             "actor_seat": None, "action_kind": None, "committed_amount": None, "pot_before": None, "action_label": outcome,
             "stacks": finals, "hole_cards": [p["hole_cards"] for p in players]}
    if steps and steps[-1]["street"] == "result":
        steps[-1] = final
    else:
        steps.append(final)
    complete_start = len(events) >= 2 and {e.get("type") for e in events[:2]} == {"small_blind", "big_blind"} and {e.get("seat") for e in events[:2]} == {0, 1}
    steps = street_wagers(steps, complete_start=complete_start)
    if equity_cache is None:
        equity_cache = {}
    # No equity from private, mucked, malformed, or merely retained hole cards.
    # This gate is independent of viewer identity; both explicit reveals and a
    # completed showdown result are required even for the owner of a folded hand.
    equity_holes = [showdown_cards.get(s, []) for s in range(2)]
    eligible = reason == "showdown" and revealed == {0, 1} and all(len(h) == 2 for h in equity_holes)
    for step in steps:
        expected = {"preflop": 0, "flop": 3, "turn": 4, "river": 5, "showdown": 5, "result": 5}.get(step["street"])
        board_known = expected is not None and len(step["board"]) == expected
        step["equity"] = showdown_equity(equity_holes, step["board"], equity_cache) if eligible and board_known else None
    return {**metadata,
            "players": players, "dealer": record.get("dealer") if type(record.get("dealer")) is int and record["dealer"] in (0, 1) else None,
            "board": board, "pot": pot, "winners": winner_names, "outcome": outcome,
            "steps": steps}


def select_highlights(hands: list[dict], *, complete: bool) -> list[dict]:
    """Earliest tie-breaks, category deduplication, chronological display, max 5."""
    hands = sorted({h["hand_id"]: h for h in hands}.values(), key=lambda h: (h["hand_number"], h["hand_id"]))
    if not hands:
        return []
    chosen: dict[int, list[str]] = {}

    def add(index: int, label: str):
        if index in chosen:
            if label not in chosen[index]:
                chosen[index].append(label)
        elif len(chosen) < 5:
            chosen[index] = [label]

    known = [i for i, h in enumerate(hands) if h["profit_a"] is not None]
    if known:
        biggest = max(known, key=lambda i: (abs(hands[i]["profit_a"]), -i))
        if hands[biggest]["profit_a"]:
            add(biggest, "Largest single-hand swing" if complete and len(known) == len(hands) else "Largest retained swing")
    if complete and len(known) == len(hands):
        scores, score = [], 0
        for h in hands:
            score += h["profit_a"]
            scores.append(score)
        # First scoring hand opens the lead. No meaningful label for ties.
        opening = next((i for i, h in enumerate(hands) if abs(h["profit_a"]) >= (h["big_blind"] or 1)), None)
        # A comeback requires erasing an actual deficit, not just winning once.
        comebacks = []
        for sign in (1, -1):
            deficit = 0
            for i, value in enumerate(scores):
                deficit = min(deficit, sign * value)
                if deficit < 0 and sign * value >= 0:
                    comebacks.append((-deficit, i))
                    deficit = 0
        if comebacks:
            recovered, index = max(comebacks, key=lambda item: (item[0], -item[1]))
            add(index, "Biggest comeback")
        previous_sign = 0
        changes = []
        for i, value in enumerate(scores):
            sign = (value > 0) - (value < 0)
            if sign and previous_sign and sign != previous_sign:
                changes.append(i)
            if sign:
                previous_sign = sign
        if changes:
            add(changes[0], "First lead change")
        if opening is not None:
            add(opening, "Opening momentum" if opening == 0 else "Early momentum")
        scoring = [i for i, h in enumerate(hands) if h["profit_a"]]
        if scoring:
            if scores[-1] == 0:
                add(scoring[-1], "Draw sealed")
            elif changes and all(value * scores[-1] > 0 for value in scores[changes[-1]:]):
                add(changes[-1], "Final lead change")
            else:
                add(scoring[-1], "Final scoring hand")
    # Fill remaining slots with the strongest retained evidence, not invented arcs.
    for i in sorted(range(len(hands)), key=lambda i: (-(abs(hands[i]["profit_a"]) if hands[i]["profit_a"] is not None else hands[i]["pot"] or 0), i)):
        if i in chosen:
            continue
        h = hands[i]
        label = "Split pot" if len(h["winners"]) == 2 else {"showdown": "Showdown", "fold": "Won after a fold", "bot_forfeit": "Bot forfeit"}.get(h["reason"], "Retained hand")
        add(i, label)
    return [{**hands[i], "label": labels[0], "labels": labels} for i, labels in sorted(chosen.items())]


def match_recap(db, matchup: dict, viewer: str | None, *, challenge_id: str | None = None) -> dict:
    # A run can contain many round-robin pairings. Match ID AND player pair are
    # checked; legacy records without a match ID are accepted only for a unique pair.
    pair_count = db.one("SELECT COUNT(*) AS n FROM matchups WHERE run_id=? AND ((player_a=? AND player_b=?) OR (player_a=? AND player_b=?))",
                        (matchup["run_id"], matchup["player_a"], matchup["player_b"], matchup["player_b"], matchup["player_a"]))["n"]
    hands = []
    # Read from one snapshot so concurrent retention cannot mix selection and
    # rendering. Stream records; retain only selection statistics for large runs.
    with db.connect() as conn:
        conn.execute("BEGIN")
        rows = conn.execute("SELECT * FROM hands WHERE run_id=? AND ((player_a=? AND player_b=?) OR (player_a=? AND player_b=?)) ORDER BY hand_number,id",
                            (matchup["run_id"], matchup["player_a"], matchup["player_b"], matchup["player_b"], matchup["player_a"]))
        for raw_row in rows:
            row = dict(raw_row)
            try:
                record = json.loads(row["record_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict) or record.get("match_id", matchup["id"] if pair_count == 1 else None) != matchup["id"]:
                continue
            normalized = normalize_hand(record, row, matchup, viewer, include_steps=False)
            hands.append({key: normalized[key] for key in ("hand_id", "hand_number", "profit_a", "pot", "big_blind", "winners", "reason")})
        complete = len(hands) == matchup["hands"]
        highlights = []
        equity_cache = {}
        for selected in select_highlights(hands, complete=complete):
            row = dict(conn.execute("SELECT * FROM hands WHERE id=? AND run_id=?", (selected["hand_id"], matchup["run_id"])).fetchone())
            normalized = normalize_hand(json.loads(row["record_json"]), row, matchup, viewer, equity_cache=equity_cache)
            highlights.append({**normalized, "label": selected["label"], "labels": selected["labels"]})
    path = f"/recaps/challenges/{quote(challenge_id, safe='')}" if challenge_id else f"/recaps/runs/{quote(matchup['run_id'], safe='')}/matches/{quote(matchup['id'], safe='')}"
    return {"schema_version": "recap-v1", "source": "direct_challenge" if challenge_id else "round_robin",
            "viewer_username": viewer, "run_id": matchup["run_id"], "matchup_id": matchup["id"],
            "players": [matchup["player_a"], matchup["player_b"]], "total_hands": matchup["hands"],
            "retained_hands": len(hands), "complete_history": complete, "playback_url": path,
            "highlights": highlights}
