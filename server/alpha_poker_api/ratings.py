"""Deterministic batch Elo ratings for one round-robin rating period."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


BASE_RATING = 1200
K_FACTOR = 32


@dataclass(frozen=True)
class EloStanding:
    rating: int
    wins: int
    losses: int
    draws: int


def expected_score(rating: int, opponent_rating: int) -> float:
    return 1.0 / (1.0 + 10.0 ** ((opponent_rating - rating) / 400.0))


def calculate_round_robin_elo(
    starting_ratings: dict[str, int],
    results: Iterable[tuple[str, str, float]],
    *,
    k_factor: int = K_FACTOR,
) -> dict[str, EloStanding]:
    """Apply one order-independent Elo rating period.

    Each result is ``(player_a, player_b, score_a)`` where score_a is 1.0 for
    a win, 0.5 for a draw, and 0.0 for a loss. Expectations are calculated
    from ratings at the start of the league, then all changes are applied at
    once after the round robin finishes.
    """

    if not starting_ratings:
        return {}
    if k_factor <= 0:
        raise ValueError("k_factor must be positive")

    deltas = {username: 0.0 for username in starting_ratings}
    records = {username: [0, 0, 0] for username in starting_ratings}
    for player_a, player_b, score_a in results:
        if player_a not in starting_ratings or player_b not in starting_ratings:
            raise ValueError("every result player must have a starting rating")
        if player_a == player_b or score_a not in {0.0, 0.5, 1.0}:
            raise ValueError("results require two distinct players and a valid score")

        expected_a = expected_score(starting_ratings[player_a], starting_ratings[player_b])
        change = k_factor * (score_a - expected_a)
        deltas[player_a] += change
        deltas[player_b] -= change
        if score_a == 1.0:
            records[player_a][0] += 1
            records[player_b][1] += 1
        elif score_a == 0.0:
            records[player_a][1] += 1
            records[player_b][0] += 1
        else:
            records[player_a][2] += 1
            records[player_b][2] += 1

    return {
        username: EloStanding(
            rating=round(starting_ratings[username] + deltas[username]),
            wins=records[username][0],
            losses=records[username][1],
            draws=records[username][2],
        )
        for username in starting_ratings
    }
