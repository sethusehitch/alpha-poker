import json

import pytest

from alpha_poker.match import play_match, summarize_profits


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
