import json

import pytest

from alpha_poker.match import (
    play_match,
    play_tournament_game,
    play_tournament_series,
    summarize_profits,
    tournament_blinds,
)


class CheckCall:
    def decide(self, state):
        return {"action": "check" if "check" in state["legal_actions"] else "call"}


def test_mirrored_identical_bots_cancel_card_and_position_luck():
    result = play_match((CheckCall(), CheckCall()), pairs=12, seed=123)
    assert result.profits == (0, 0)
    assert result.bb_per_100 == (0.0, 0.0)
    assert len(result.hand_histories) == 24
    for first, mirror in zip(result.hand_histories[::2], result.hand_histories[1::2]):
        assert first["hole_cards"] == mirror["hole_cards"]
        assert first["board"] == mirror["board"]
        assert first["seat_to_bot"] == [0, 1]
        assert mirror["seat_to_bot"] == [1, 0]
    json.dumps(result.to_dict())


def test_match_is_deterministic():
    kwargs = {"pairs": 5, "seed": 999, "match_id": "same"}
    left = play_match((CheckCall(), CheckCall()), **kwargs)
    right = play_match((CheckCall(), CheckCall()), **kwargs)
    assert left.to_dict() == right.to_dict()


def test_statistics_are_in_bb100_and_zero_sum():
    summary = summarize_profits([100, -50, 200, -100], big_blind=100, cluster_size=2)
    assert summary["bb_per_100"] == pytest.approx(37.5)
    assert summary["standard_error"] > 0
    assert summary["confidence_95"][0] < summary["bb_per_100"] < summary["confidence_95"][1]


def test_requires_complete_clusters():
    with pytest.raises(ValueError):
        summarize_profits([1, 2, 3], big_blind=100, cluster_size=2)


class PotAggressor:
    def decide(self, state):
        if "raise" in state["legal_actions"]:
            return {"action": "raise", "amount": state["max_raise_to"]}
        return {"action": "check" if "check" in state["legal_actions"] else "call"}


def test_tournament_blinds_escalate_on_documented_boundaries():
    assert tournament_blinds(1) == tournament_blinds(10) == (50, 100)
    assert tournament_blinds(11) == tournament_blinds(20) == (100, 200)
    assert tournament_blinds(21) == (200, 400)
    assert tournament_blinds(31) == (400, 800)
    assert tournament_blinds(41) == (800, 1600)
    assert tournament_blinds(51) == (1600, 3200)
    assert tournament_blinds(61) == (3200, 6400)
    assert tournament_blinds(71) == (5000, 10000)


def test_passive_bots_still_finish_when_blinds_force_all_in():
    result = play_tournament_game(
        (CheckCall(), CheckCall()), game_number=1, seed=89,
        match_id="forced-finish", timeout_seconds=0.25,
    )
    assert result.hands <= 71
    assert 0 in result.final_stacks


def test_final_level_uses_the_shorter_stack_and_ends_at_bankruptcy():
    result = play_tournament_game(
        (CheckCall(), CheckCall()), game_number=1, seed=89,
        match_id="forced-finish", timeout_seconds=0.25,
    )
    final = result.hand_histories[-1]
    if final["hand_number"] >= 71:
        effective_stack = min(final["starting_stacks"])
        assert final["blinds"] == {"small": effective_stack, "big": effective_stack}
    assert sum(result.final_stacks) == 20_000
    assert 0 in result.final_stacks


def test_tournament_game_carries_stacks_until_bankruptcy():
    result = play_tournament_game(
        (PotAggressor(), CheckCall()), game_number=1, seed=313,
        match_id="tournament", timeout_seconds=0.25,
    )
    assert result.final_stacks in {(20_000, 0), (0, 20_000)}
    assert result.hands == len(result.hand_histories)
    assert result.hand_histories[1]["starting_stacks"] == result.hand_histories[0]["final_stacks"]
    assert all(history["game"] == "PLHE" for history in result.hand_histories)
    assert sum(result.pots_won) <= result.hands


def test_best_of_five_stops_at_three_wins_and_is_deterministic():
    kwargs = {
        "bots": (PotAggressor(), CheckCall()), "seed": 717,
        "bot_names": ("Aggressor", "Caller"), "match_id": "series",
        "timeout_seconds": 0.25,
    }
    first = play_tournament_series(**kwargs)
    second = play_tournament_series(**kwargs)
    assert first.to_dict() == second.to_dict()
    assert 3 <= len(first.games) <= 5
    assert max(first.score) == 3
    assert sum(first.score) == len(first.games)
    assert first.hands == sum(game.hands for game in first.games)
