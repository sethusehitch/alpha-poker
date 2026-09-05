"""Mirrored match scheduling and statistical summaries."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Sequence

from .engine import Bot, HandResult, play_hand, shuffled_deal


@dataclass(frozen=True)
class MatchResult:
    match_id: str
    seed: int
    hands: int
    bot_names: tuple[str, str]
    profits: tuple[int, int]
    bb_per_100: tuple[float, float]
    standard_error: tuple[float, float]
    confidence_95: tuple[tuple[float, float], tuple[float, float]]
    hand_histories: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "seed": self.seed,
            "hands": self.hands,
            "bot_names": list(self.bot_names),
            "profits": list(self.profits),
            "bb_per_100": list(self.bb_per_100),
            "standard_error": list(self.standard_error),
            "confidence_95": [list(interval) for interval in self.confidence_95],
            "hand_histories": list(self.hand_histories),
        }


def summarize_profits(
    profits_chips: Sequence[int],
    *,
    big_blind: int,
    cluster_size: int = 1,
) -> dict[str, Any]:
    """Summarize hand profits, clustering mirrored pairs for uncertainty."""
    if not profits_chips or big_blind <= 0 or cluster_size <= 0:
        raise ValueError("profits, a positive blind, and a positive cluster size are required")
    if len(profits_chips) % cluster_size:
        raise ValueError("profit count must be divisible by cluster size")
    values_bb = [profit / big_blind for profit in profits_chips]
    mean_bb_per_hand = statistics.fmean(values_bb)
    clusters = [
        statistics.fmean(values_bb[i : i + cluster_size])
        for i in range(0, len(values_bb), cluster_size)
    ]
    se_per_hand = statistics.stdev(clusters) / math.sqrt(len(clusters)) if len(clusters) > 1 else 0.0
    bb100 = mean_bb_per_hand * 100
    se100 = se_per_hand * 100
    return {
        "hands": len(values_bb),
        "total_chips": sum(profits_chips),
        "bb_per_100": bb100,
        "standard_error": se100,
        "confidence_95": (bb100 - 1.96 * se100, bb100 + 1.96 * se100),
    }


def play_match(
    bots: Sequence[Bot],
    *,
    pairs: int,
    seed: int,
    bot_names: tuple[str, str] = ("bot_a", "bot_b"),
    match_id: str = "match-1",
    starting_stack: int = 10_000,
    small_blind: int = 50,
    big_blind: int = 100,
    timeout_seconds: float = 1.0,
) -> MatchResult:
    """Play duplicate deals. In the mirror, bots swap seats and hole cards."""
    if len(bots) != 2 or pairs <= 0:
        raise ValueError("play_match requires two bots and at least one pair")
    histories: list[dict[str, Any]] = []
    bot_profits: list[list[int]] = [[], []]
    for pair_index in range(pairs):
        deal_seed = seed + pair_index
        deal = shuffled_deal(deal_seed)
        strategy_seeds = (seed * 1_000_003 + pair_index * 2, seed * 1_000_003 + pair_index * 2 + 1)
        first = play_hand(
            bots,
            seed=deal_seed,
            hand_id=f"{match_id}-{pair_index + 1}a",
            match_id=match_id,
            hand_number=pair_index * 2 + 1,
            dealer=0,
            starting_stack=starting_stack,
            small_blind=small_blind,
            big_blind=big_blind,
            timeout_seconds=timeout_seconds,
            bot_random_seeds=strategy_seeds,
            deal=deal,
        )
        second = play_hand(
            (bots[1], bots[0]),
            seed=deal_seed,
            hand_id=f"{match_id}-{pair_index + 1}b",
            match_id=match_id,
            hand_number=pair_index * 2 + 2,
            dealer=0,
            starting_stack=starting_stack,
            small_blind=small_blind,
            big_blind=big_blind,
            timeout_seconds=timeout_seconds,
            bot_random_seeds=(strategy_seeds[1], strategy_seeds[0]),
            deal=deal,
        )
        _record(first, (0, 1), bot_profits, histories)
        _record(second, (1, 0), bot_profits, histories)

    summaries = [summarize_profits(p, big_blind=big_blind, cluster_size=2) for p in bot_profits]
    return MatchResult(
        match_id=match_id,
        seed=seed,
        hands=pairs * 2,
        bot_names=bot_names,
        profits=(sum(bot_profits[0]), sum(bot_profits[1])),
        bb_per_100=(summaries[0]["bb_per_100"], summaries[1]["bb_per_100"]),
        standard_error=(summaries[0]["standard_error"], summaries[1]["standard_error"]),
        confidence_95=(summaries[0]["confidence_95"], summaries[1]["confidence_95"]),
        hand_histories=tuple(histories),
    )


def _record(
    result: HandResult,
    seat_to_bot: tuple[int, int],
    bot_profits: list[list[int]],
    histories: list[dict[str, Any]],
) -> None:
    history = dict(result.history)
    history["seat_to_bot"] = list(seat_to_bot)
    history["bot_profits"] = [0, 0]
    for seat, bot_index in enumerate(seat_to_bot):
        profit = result.profits[seat]
        bot_profits[bot_index].append(profit)
        history["bot_profits"][bot_index] = profit
    histories.append(history)
