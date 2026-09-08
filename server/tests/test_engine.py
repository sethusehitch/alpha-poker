import json
import time

import pytest

import alpha_poker.engine as engine_module
from alpha_poker.engine import HoldemHand, play_hand


class CheckCall:
    def decide(self, state):
        return {"action": "check" if "check" in state["legal_actions"] else "call"}


def test_runner_with_its_own_deadline_does_not_create_a_thread_per_decision(monkeypatch):
    class DeadlineBot(CheckCall):
        _alpha_poker_enforces_timeout = True

    class UnexpectedExecutor:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("the engine must trust the runner's process deadline")

    monkeypatch.setattr(engine_module, "ThreadPoolExecutor", UnexpectedExecutor)
    result = play_hand((DeadlineBot(), DeadlineBot()), seed=101)
    assert result.history["events"][-1]["type"] == "result"


def test_preflop_and_street_progression():
    hand = HoldemHand(hand_id="h", seed=7)
    assert hand.pot == 150
    assert hand.actor == hand.dealer
    hand.act({"type": "call"})
    assert hand.street == "preflop"
    hand.act({"type": "check"})
    assert hand.street == "flop"
    assert len(hand.board) == 3
    assert hand.actor == 1 - hand.dealer


def test_raise_accounting_and_fold():
    hand = HoldemHand(hand_id="h", seed=8)
    hand.act({"type": "raise", "to": 300})
    assert hand.pot == 400
    assert hand.stacks[0] == 9700
    hand.act({"type": "fold"})
    result = hand.result()
    assert result.profits == (100, -100)
    assert sum(result.profits) == 0


def test_invalid_bot_action_folds_when_facing_bet():
    result = play_hand((lambda state: {"action": "dance"}, CheckCall()), seed=2)
    assert result.profits == (-50, 50)
    assert any(event["type"] == "bot_error" for event in result.history["events"])


def test_timeout_forfeits_even_when_check_was_available():
    class Slow:
        def decide(self, state):
            time.sleep(0.03)
            return {"action": "check"}

    # Slow seat is big blind and forfeits, even though check was strategically legal.
    result = play_hand((CheckCall(), Slow()), seed=3, timeout_seconds=0.001)
    errors = [event for event in result.history["events"] if event["type"] == "bot_error"]
    assert errors and errors[0]["fallback"] == "forfeit"
    assert result.history["events"][-1]["reason"] == "bot_forfeit"
    json.dumps(result.history)


def test_all_in_runs_complete_board():
    class Jam:
        def decide(self, state):
            return {"action": "all_in"}

    result = play_hand((Jam(), CheckCall()), seed=4)
    assert len(result.history["board"]) == 5
    assert sum(result.profits) == 0
    showdown = next(event for event in result.history["events"] if event["type"] == "showdown")
    assert len(showdown["hands"]) == 2
    assert all(hand["category"] for hand in showdown["hands"])
    assert result.history["pot"] == 20_000


def test_all_in_can_be_a_call():
    hand = HoldemHand(hand_id="h", seed=5, starting_stack=200)
    hand.act({"type": "all_in"})
    assert hand.street_contrib == [200, 100]
    hand.act({"type": "all_in"})
    assert hand.finished
    assert len(hand.result().history["board"]) == 5


def test_short_all_in_is_not_advertised_as_a_regular_raise():
    hand = HoldemHand(hand_id="h", seed=6, starting_stack=250)
    hand.act({"type": "raise", "to": 200})
    legal = {action["type"]: action for action in hand.legal_actions()}
    assert "raise" not in legal
    assert legal["all_in"]["to"] == 250


def test_illegal_under_raise_rejected():
    hand = HoldemHand(hand_id="h", seed=9)
    with pytest.raises(ValueError):
        hand.act({"type": "raise", "to": 150})


def test_public_bot_contract_matches_starter_kit():
    hand = HoldemHand(
        hand_id="h",
        match_id="m",
        hand_number=7,
        seed=10,
        decision_deadline_ms=250,
        bot_random_seeds=(41, 42),
    )
    state = hand.bot_state(0)
    assert state["schema_version"] == "2026-09-01"
    assert state["match_id"] == "m" and state["hand_number"] == 7
    assert state["seat"] == 0 and state["button_seat"] == 0
    assert state["community_cards"] == []
    assert state["stacks"] == {"0": 9950, "1": 9900}
    assert state["committed"] == {"0": 50, "1": 100}
    assert state["min_raise_to"] == 200 and state["max_raise_to"] == 10000
    assert state["legal_actions"] == ["fold", "call", "raise", "all_in"]
    assert state["decision_deadline_ms"] == 250 and state["bot_random_seed"] == 41


def test_pot_limit_caps_preflop_raise_at_the_size_of_the_pot():
    hand = HoldemHand(hand_id="plhe", seed=11, betting_limit="pot_limit")
    legal = {action["type"]: action for action in hand.legal_actions()}
    assert legal["raise"] == {"type": "raise", "min_to": 200, "max_to": 300}
    assert "all_in" not in legal


def test_persistent_unequal_stacks_are_conserved():
    hand = HoldemHand(
        hand_id="persistent", seed=12, betting_limit="pot_limit",
        starting_stacks=(2_500, 17_500),
    )
    while not hand.finished:
        legal = {action["type"]: action for action in hand.legal_actions()}
        hand.act({"type": "check" if "check" in legal else "call"})
    result = hand.result()
    assert result.history["starting_stacks"] == [2_500, 17_500]
    assert sum(result.history["final_stacks"]) == 20_000
    assert sum(result.profits) == 0


def test_short_all_in_call_returns_uncalled_chips_and_reaches_showdown():
    result = play_hand(
        (CheckCall(), CheckCall()), hand_id="short-call", seed=13,
        starting_stacks=(80, 1_000), small_blind=50, big_blind=100,
        betting_limit="pot_limit",
    )
    returns = [event for event in result.history["events"] if event["type"] == "uncalled_return"]
    assert returns == [{"type": "uncalled_return", "seat": 1, "amount": 20, "street": "preflop"}]
    assert result.history["events"][-1]["reason"] == "showdown"
    assert sum(result.history["final_stacks"]) == 1_080


def test_equal_forced_blinds_create_a_fair_immediate_showdown():
    result = play_hand(
        (CheckCall(), CheckCall()), hand_id="sudden-death", seed=14,
        starting_stacks=(3_000, 17_000), small_blind=3_000, big_blind=3_000,
        betting_limit="pot_limit",
    )
    assert result.history["pot"] == 6_000
    assert result.history["events"][-1]["reason"] == "showdown"
    assert sum(result.history["final_stacks"]) == 20_000
