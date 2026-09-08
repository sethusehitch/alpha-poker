from copy import deepcopy
from itertools import combinations
from time import perf_counter

import pytest

from alpha_poker.engine import play_hand
from alpha_poker.evaluator import evaluate
from alpha_poker_api import recaps
from alpha_poker_api.recap_equity import DECK, PREFLOP_SAMPLES, _calculate, showdown_equity
from test_recaps import hand_record, normalized, MATCH


def multi_street_record():
    def bot(state):
        target = {"preflop": 120, "flop": 80, "turn": 140, "river": 200}[state["street"]]
        if "raise" in state["legal_actions"] and state["min_raise_to"] <= target <= state["max_raise_to"]:
            return {"action": "raise", "amount": target}
        return {"action": "check" if "check" in state["legal_actions"] else "call"}
    record = play_hand([bot, bot], seed=7, hand_id="hand_1", starting_stack=2000, small_blind=10, big_blind=20).to_dict()
    record["players"] = ["alice", "bob"]
    return record


@pytest.mark.parametrize("mirror", [False, True])
def test_wagers_accumulate_and_gather_once_per_street_without_double_counting(mirror):
    record = multi_street_record()
    record["seat_to_bot"] = [1, 0] if mirror else [0, 1]
    hand = normalized(record)
    assert hand["steps"][0]["table_chips"]["wagers"] == [10, 0]
    assert hand["steps"][1]["table_chips"]["wagers"] == [10, 20]
    assert hand["steps"][2]["committed_amount"] == 110  # not raise-to 120
    assert hand["steps"][2]["table_chips"]["wagers"] == [120, 20]
    sweeps = [s for s in hand["steps"] if s["table_chips"]["phase"] == "sweep"]
    assert [s["table_chips"]["sweep"] for s in sweeps] == [[120, 120], [80, 80], [140, 140], [200, 200]]
    assert [s["table_chips"]["gathered_pot"] for s in sweeps] == [240, 400, 680, 1080]
    for step in hand["steps"]:
        ledger = step["table_chips"]
        assert ledger["gathered_pot"] + sum(ledger["wagers"]) == step["pot"]
        if step["street"] != "result":
            assert sum(step["stacks"]) + ledger["gathered_pot"] + sum(ledger["wagers"]) == 4000
        if ledger["phase"] == "sweep":
            assert step["actor_seat"] is None
            assert ledger["wagers"] == [0, 0]
            assert ledger["gathered_before"] + sum(ledger["sweep"]) == ledger["gathered_pot"]
    assert sum(hand["steps"][-1]["stacks"]) == 4000


@pytest.mark.parametrize("kind,pot", [("fold", 30), ("all_in", 4000)])
def test_preflop_fold_and_all_in_runout_gather_before_award(kind, pot):
    hand = normalized(hand_record(kind))
    sweeps = [s for s in hand["steps"] if s["table_chips"]["phase"] == "sweep"]
    assert len(sweeps) == 1 and sweeps[0]["street"] == "preflop"
    assert sweeps[0]["board"] == []
    assert sum(sweeps[0]["table_chips"]["sweep"]) == pot
    assert sum(sweeps[0]["stacks"]) == 4000 - pot
    assert hand["steps"][-1]["table_chips"]["gathered_pot"] == pot
    assert hand["steps"][-1]["table_chips"]["wagers"] == [0, 0]


def test_missing_payment_is_unknown_not_inferred_from_a_total():
    record = hand_record()
    del record["events"][2]["amount"]
    hand = normalized(record)
    assert hand["steps"][2]["table_chips"]["wagers"] == [None, 20]
    sweep = next(s for s in hand["steps"] if s["table_chips"]["phase"] == "sweep")
    assert sweep["table_chips"]["sweep"] == [None, 20]
    assert sweep["table_chips"]["gathered_pot"] == 40  # recorded authoritative total after gathering
    assert sweep["table_chips"]["wagers"] == [0, 0]


def test_missing_board_boundary_uses_next_street_and_does_not_invent_flop_odds():
    record = multi_street_record()
    record["events"] = [e for e in record["events"] if not (e["type"] == "board" and e["street"] == "flop")]
    hand = normalized(record)
    flop = next(s for s in hand["steps"] if s["street"] == "flop")
    assert flop["table_chips"]["gathered_pot"] == 240
    assert flop["equity"] is None
    assert flop["board"] == []


def test_legacy_fragment_does_not_invent_initial_wagers_or_flights():
    record = hand_record()
    record["events"] = record["events"][2:]
    first = normalized(record)["steps"][0]
    assert first["table_chips"]["gathered_pot"] is None
    assert first["table_chips"]["wagers"] == [None, None]
    no_events = normalized({"players": ["alice", "bob"], "pot": 200, "events": []})
    assert len(no_events["steps"]) == 1
    assert no_events["steps"][0]["table_chips"]["gathered_pot"] == 200


def test_exact_equity_matches_enumeration_and_splits_ties():
    holes, flop = [["As", "Kd"], ["9s", "9h"]], ["Ts", "Jd", "Qc"]
    remaining = [c for c in DECK if c not in holes[0] + holes[1] + flop]
    points = 0
    for tail in combinations(remaining, 2):
        a, b = (evaluate(h + flop + list(tail)) for h in holes)
        points += 2 if a > b else 1 if a == b else 0
    value = showdown_equity(holes, flop)
    assert value["method"] == "exact" and value["trials"] == 990
    assert value["percentages"][0] == round(points * 500 / 990) / 10
    assert showdown_equity(holes, flop + ["Kh"])["trials"] == 44
    assert showdown_equity(holes, flop + ["Kh", "2c"])["percentages"] == [100, 0]
    tie = showdown_equity([["2c", "3d"], ["4c", "5d"]], ["As", "Ks", "Qs", "Js", "Ts"])
    assert tie["percentages"] == [50, 50] and tie["trials"] == 1 and tie["tie_policy"] == "split"


def test_preflop_estimate_is_deterministic_complementary_and_seat_symmetric():
    holes = [["As", "Kd"], ["9s", "9h"]]
    first = showdown_equity(holes, [])
    assert first["method"] == "estimated" and first["trials"] == PREFLOP_SAMPLES
    assert first["sampling_error_pp"] == 2.2
    assert sum(first["percentages"]) == 100
    assert showdown_equity(list(reversed(holes)), [])["percentages"] == list(reversed(first["percentages"]))
    _calculate.cache_clear()
    assert first == showdown_equity(holes, [])
    symmetric = showdown_equity([["As", "Ah"], ["Ac", "Ad"]], [])
    assert abs(symmetric["percentages"][0] - 50) < 2.2


@pytest.mark.parametrize("kind", ["fold", "mucked", "missing_reveal", "forfeit"])
def test_private_holes_never_produce_equity_even_for_the_viewer(kind, monkeypatch):
    record = hand_record("fold" if kind == "fold" else "showdown")
    if kind in ("mucked", "missing_reveal"):
        for event in record["events"]:
            if event["type"] == "showdown":
                event["hands"] = event["hands"][:1] if kind == "mucked" else []
    if kind == "forfeit":
        record["events"][-1]["reason"] = "bot_forfeit"
    def forbidden(*args):
        pytest.fail("Hidden equity must not be computed at all")
    monkeypatch.setattr(recaps, "showdown_equity", forbidden)
    assert all(s["equity"] is None for s in normalized(record)["steps"])


def test_equity_ignores_future_board_and_mirrored_names_do_not_change_physical_odds():
    record = hand_record(mirror=True)
    hand = normalized(record)
    assert hand["players"][1]["username"] == "alice"
    assert hand["steps"][-1]["equity"]["percentages"] == [100, 0]
    changed = deepcopy(record)
    changed["board"][-1] = "8c"
    assert normalized(changed)["steps"][0]["equity"] == hand["steps"][0]["equity"]
    assert hand["steps"][0]["hole_cards"][0] == []
    assert hand["steps"][0]["equity"]["method"] == "estimated"  # retrospective only after actual showdown


def test_invalid_cards_and_selection_only_are_safe(monkeypatch):
    assert showdown_equity([["As", "As"], ["9s", "9h"]], []) is None
    assert showdown_equity([["As", "Kd"], ["9s", "9h"]], ["As", "Jd", "Qc"]) is None
    monkeypatch.setattr(recaps, "showdown_equity", lambda *args: pytest.fail("Selection must stay cheap"))
    value = recaps.normalize_hand(hand_record(), {"id":"h", "hand_number":1}, MATCH, "alice", include_steps=False)
    assert "steps" not in value


def test_missing_showdown_board_does_not_show_a_preflop_estimate():
    record = hand_record()
    record["board"] = []
    record["events"] = [e for e in record["events"] if e["type"] != "board"]
    hand = normalized(record)
    assert all(s["equity"] is None for s in hand["steps"] if s["street"] in {"showdown", "result"})


def test_unknown_legacy_action_preserves_explicit_paid_amount():
    record = hand_record()
    record["events"][2]["action"] = "legacy_payment"
    step = normalized(record)["steps"][2]
    assert step["action_kind"] is None
    assert step["committed_amount"] == 10
    assert step["table_chips"]["wagers"] == [20, 20]


def test_five_distinct_equity_hands_performance_and_cache_guard():
    _calculate.cache_clear()
    pairs = [list(map(list, pair)) for pair in [
        (("As","Kd"),("9s","9h")), (("Ah","Ad"),("Kc","Ks")), (("7s","8s"),("Tc","Td")),
        (("2h","2d"),("Qc","Js")), (("Ac","Qd"),("Kh","Jh")),
    ]]
    cache = {}
    start = perf_counter()
    for holes in pairs:
        board = [c for c in DECK if c not in holes[0] + holes[1]][:5]
        for count in (0, 3, 4, 5):
            showdown_equity(holes, board[:count], cache)
    cold = perf_counter() - start
    # Local target <=2.5s, with scheduling headroom in the hard regression guard.
    assert cold < 3.5, f"Five cold highlighted hands exceeded request guard: {cold:.2f}s"
    misses = _calculate.cache_info().misses
    start = perf_counter()
    for _ in range(20):
        for holes in pairs:
            showdown_equity(holes, [], cache)
    assert _calculate.cache_info().misses == misses
    assert perf_counter() - start < .5
