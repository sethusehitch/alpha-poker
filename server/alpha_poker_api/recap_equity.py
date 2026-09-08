"""Retrospective showdown equity, with an engine-oracle-tested seven-card ranker.

Preflop: 2,048 uniformly sampled distinct boards, fixed seed. Worst-case
binomial standard error is ~1.10 percentage points (~2.2pp at 95%). Flop,
turn, river: exact enumeration. A tie contributes half a win to each seat.
Callers must authorize the recap and verify BOTH hands were actually shown.
"""
from functools import lru_cache
from itertools import combinations
from random import Random
from math import sqrt

from alpha_poker.evaluator import RANKS, SUITS, RANK_VALUE

PREFLOP_SAMPLES = 2048
EQUITY_SEED = 20260907
DECK = tuple(rank + suit for rank in RANKS for suit in SUITS)


def _straight(ranks):
    values = set(ranks)
    if 14 in values:
        values.add(1)
    for high in range(14, 5 - 1, -1):
        if all(rank in values for rank in range(high - 4, high + 1)):
            return high
    return 0


def _seven(cards):
    """Rank seven already-validated distinct cards without 21 subset evaluations.

    Private to recap odds; gameplay continues to use the independent engine
    evaluator. Return exactly the engine's lexicographic category/kicker tuple.
    """
    counts = {}
    suits = {}
    for card in cards:
        rank = RANK_VALUE[card[0]]
        counts[rank] = counts.get(rank, 0) + 1
        suits.setdefault(card[1], []).append(rank)
    ranks = sorted(counts, reverse=True)
    flush = next((sorted(values, reverse=True) for values in suits.values() if len(values) >= 5), None)
    if flush:
        high = _straight(flush)
        if high:
            return (8, high)
    quads = [r for r in ranks if counts[r] == 4]
    if quads:
        return (7, quads[0], next(r for r in ranks if r != quads[0]))
    trips = [r for r in ranks if counts[r] >= 3]
    pairs = [r for r in ranks if counts[r] >= 2]
    if trips and len(pairs) >= 2:
        return (6, trips[0], next(r for r in pairs if r != trips[0]))
    if flush:
        return (5, *flush[:5])
    high = _straight(ranks)
    if high:
        return (4, high)
    if trips:
        return (3, trips[0], *[r for r in ranks if r != trips[0]][:2])
    if len(pairs) >= 2:
        return (2, *pairs[:2], next(r for r in ranks if r not in pairs[:2]))
    if pairs:
        return (1, pairs[0], *[r for r in ranks if r != pairs[0]][:3])
    return (0, *ranks[:5])


@lru_cache(maxsize=128)
def _calculate(left: tuple[str, ...], right: tuple[str, ...], board: tuple[str, ...]):
    remaining = tuple(card for card in DECK if card not in left + right + board)
    needed = 5 - len(board)
    if needed == 5:
        rng = Random(EQUITY_SEED)
        sampled = set()
        while len(sampled) < PREFLOP_SAMPLES:
            sampled.add(tuple(sorted(rng.sample(remaining, 5))))
        runouts = sorted(sampled)
        method = "estimated"
    else:
        runouts = combinations(remaining, needed)
        method = "exact"
    points, trials = 0, 0
    for tail in runouts:
        a, b = _seven(left + board + tail), _seven(right + board + tail)
        points += 2 if a > b else 1 if a == b else 0
        trials += 1
    # Round one side and complement it, so displayed values sum to 100%.
    tenths = round(points * 500 / trials)
    return tenths, method, trials


def showdown_equity(holes: list[list[str]], board: list[str], cache: dict | None = None) -> dict | None:
    if len(holes) != 2 or any(len(h) != 2 for h in holes) or len(board) not in (0, 3, 4, 5):
        return None
    used = holes[0] + holes[1] + board
    if len(set(used)) != len(used) or any(c not in DECK for c in used):
        return None
    seats = [tuple(sorted(h)) for h in holes]
    reverse = seats[0] > seats[1]
    key = (*sorted(seats), tuple(sorted(board)))
    # This per-construction cache also avoids repeated wrapper/validation work
    # across the same board's action steps. The LRU is bounded and has no identity.
    if cache is None:
        cache = {}
    if key not in cache:
        cache[key] = _calculate(*key)
    tenths, method, trials = cache[key]
    if reverse:
        tenths = 1000 - tenths
    return {"version": "showdown-equity-v1", "percentages": [tenths / 10, (1000 - tenths) / 10],
            "method": method, "trials": trials, "tie_policy": "split",
            "sampling_error_pp": round(1.96 * 50 / sqrt(trials), 1) if method == "estimated" else None}
