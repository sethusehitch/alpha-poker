import pytest

from alpha_poker.evaluator import compare, evaluate


@pytest.mark.parametrize(
    "strong,weak",
    [
        (["As", "Ks", "Qs", "Js", "Ts", "2c", "3d"], ["Ac", "Ad", "Ah", "As", "2d", "3c", "4h"]),
        (["Ac", "2d", "3h", "4s", "5c", "Kd", "Qh"], ["Ac", "Ad", "Kh", "Qs", "Jc", "9d", "2h"]),
        (["Ah", "Ad", "Ac", "Kh", "Kd", "Ks", "2c"], ["Qh", "Qd", "Qc", "Jh", "Jd", "9s", "2d"]),
    ],
)
def test_rank_order(strong, weak):
    assert compare(strong, weak) == 1


def test_best_five_and_tie():
    board = ["As", "Ks", "Qs", "Js", "Ts"]
    assert compare(board + ["2c", "3d"], board + ["9c", "9d"]) == 0
    assert evaluate(board + ["2c", "3d"])[0] == 8


def test_rejects_duplicate_cards():
    with pytest.raises(ValueError):
        evaluate(["As", "As", "Qs", "Js", "Ts"])
