"""Dependency-free 5-of-7 Texas Hold'em hand evaluator."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Iterable, Sequence

RANKS = "23456789TJQKA"
SUITS = "cdhs"
RANK_VALUE = {rank: value for value, rank in enumerate(RANKS, start=2)}
CATEGORY_NAMES = (
    "high_card",
    "one_pair",
    "two_pair",
    "three_of_a_kind",
    "straight",
    "flush",
    "full_house",
    "four_of_a_kind",
    "straight_flush",
)


def validate_card(card: str) -> None:
    if len(card) != 2 or card[0] not in RANKS or card[1] not in SUITS:
        raise ValueError(f"invalid card: {card!r}")


def _five(cards: Sequence[str]) -> tuple[int, ...]:
    ranks = sorted((RANK_VALUE[c[0]] for c in cards), reverse=True)
    counts = Counter(ranks)
    groups = sorted(((count, rank) for rank, count in counts.items()), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    unique = sorted(set(ranks), reverse=True)
    if 14 in unique:
        unique.append(1)
    straight_high = next(
        (unique[i] for i in range(len(unique) - 4) if unique[i] - unique[i + 4] == 4),
        None,
    )

    if flush and straight_high:
        return (8, straight_high)
    if groups[0][0] == 4:
        quad = groups[0][1]
        return (7, quad, max(rank for rank in ranks if rank != quad))
    trips = sorted((rank for rank, count in counts.items() if count == 3), reverse=True)
    pairs = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)
    if trips and (pairs or len(trips) > 1):
        return (6, trips[0], pairs[0] if pairs else trips[1])
    if flush:
        return (5, *ranks)
    if straight_high:
        return (4, straight_high)
    if trips:
        kickers = sorted((rank for rank in ranks if rank != trips[0]), reverse=True)[:2]
        return (3, trips[0], *kickers)
    if len(pairs) >= 2:
        high, low = pairs[:2]
        kicker = max(rank for rank in ranks if rank not in (high, low))
        return (2, high, low, kicker)
    if pairs:
        kickers = sorted((rank for rank in ranks if rank != pairs[0]), reverse=True)[:3]
        return (1, pairs[0], *kickers)
    return (0, *ranks)


def evaluate(cards: Iterable[str]) -> tuple[int, ...]:
    """Return a lexicographically comparable rank for five through seven cards."""
    cards = tuple(cards)
    if not 5 <= len(cards) <= 7:
        raise ValueError("evaluate expects between five and seven cards")
    for card in cards:
        validate_card(card)
    if len(set(cards)) != len(cards):
        raise ValueError("cards must be unique")
    return max(_five(combo) for combo in combinations(cards, 5))


def compare(left: Iterable[str], right: Iterable[str]) -> int:
    """Return 1 when left wins, -1 when right wins, and 0 for a tie."""
    a, b = evaluate(left), evaluate(right)
    return (a > b) - (a < b)


def describe(rank: Sequence[int]) -> str:
    """Return the stable machine-readable category name for an evaluated rank."""
    if not rank or not 0 <= rank[0] < len(CATEGORY_NAMES):
        raise ValueError("invalid evaluated rank")
    return CATEGORY_NAMES[rank[0]]
