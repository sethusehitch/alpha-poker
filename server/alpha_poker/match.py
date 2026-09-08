"""Mirrored match scheduling and statistical summaries."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .engine import Bot, HandResult, play_hand, shuffled_deal

TOURNAMENT_STARTING_STACK = 10_000
BLIND_LEVELS = (
    (10, 50, 100),
    (20, 100, 200),
    (30, 200, 400),
    (40, 400, 800),
    (50, 800, 1_600),
    (60, 1_600, 3_200),
    (70, 3_200, 6_400),
    # The final level is replaced with current-stack-sized blinds by
    # ``play_tournament_game``. These values remain the public schedule floor.
    (None, 5_000, 10_000),
)
FINAL_BLIND_LEVEL_HAND = 71
MAX_TOURNAMENT_HANDS = 100


@dataclass(frozen=True)
class TournamentGameResult:
    game_number: int
    winner: int
    hands: int
    final_stacks: tuple[int, int]
    pots_won: tuple[int, int]
    all_ins_won: tuple[int, int]
    showdowns_won: tuple[int, int]
    folds_forced: tuple[int, int]
    hand_histories: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class TournamentSeriesResult:
    match_id: str
    seed: int
    bot_names: tuple[str, str]
    winner: int
    score: tuple[int, int]
    hands: int
    games: tuple[TournamentGameResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "2.0",
            "match_id": self.match_id,
            "seed": self.seed,
            "format": "best_of_five_plhe",
            "bot_names": list(self.bot_names),
            "winner": self.bot_names[self.winner],
            "winner_index": self.winner,
            "series_score": list(self.score),
            "hands": self.hands,
            "games": [
                {
                    "game_number": game.game_number,
                    "winner": self.bot_names[game.winner],
                    "winner_index": game.winner,
                    "hands": game.hands,
                    "final_stacks": list(game.final_stacks),
                    "pots_won": list(game.pots_won),
                    "all_ins_won": list(game.all_ins_won),
                    "showdowns_won": list(game.showdowns_won),
                    "folds_forced": list(game.folds_forced),
                }
                for game in self.games
            ],
        }


def tournament_blinds(hand_number: int) -> tuple[int, int]:
    if hand_number <= 0:
        raise ValueError("hand_number must be positive")
    for through_hand, small, big in BLIND_LEVELS:
        if through_hand is None or hand_number <= through_hand:
            return small, big
    raise AssertionError("unreachable blind schedule")


def play_tournament_game(
    bots: Sequence[Bot],
    *,
    game_number: int,
    seed: int,
    match_id: str,
    first_dealer: int = 0,
    starting_stack: int = TOURNAMENT_STARTING_STACK,
    timeout_seconds: float = 1.0,
    max_hands: int = MAX_TOURNAMENT_HANDS,
) -> TournamentGameResult:
    """Play one persistent-stack PLHE game until a bot owns all chips."""
    if len(bots) != 2 or game_number <= 0 or first_dealer not in {0, 1}:
        raise ValueError("a tournament game requires two bots and a valid game/dealer")
    stacks = [starting_stack, starting_stack]
    histories: list[dict[str, Any]] = []
    pots_won = [0, 0]
    all_ins_won = [0, 0]
    showdowns_won = [0, 0]
    folds_forced = [0, 0]
    for hand_number in range(1, max_hands + 1):
        small, big = tournament_blinds(hand_number)
        if hand_number >= FINAL_BLIND_LEVEL_HAND:
            # Commit the shorter stack from both players before dealing. This
            # is a fair heads-up all-in: the deeper stack keeps its unmatched
            # chips, and every non-tied hand ends in genuine bankruptcy. If
            # the short stack wins, sudden death repeats with the new stacks.
            effective_stack = min(stacks)
            small, big = effective_stack, effective_stack
        result = play_hand(
            bots,
            seed=seed + hand_number - 1,
            hand_id=f"{match_id}-g{game_number}-h{hand_number}",
            match_id=match_id,
            hand_number=hand_number,
            dealer=(first_dealer + hand_number - 1) % 2,
            starting_stacks=(stacks[0], stacks[1]),
            small_blind=small,
            big_blind=big,
            betting_limit="pot_limit",
            timeout_seconds=timeout_seconds,
            bot_random_seeds=(seed * 1_000_003 + hand_number * 2, seed * 1_000_003 + hand_number * 2 + 1),
        )
        history = dict(result.history)
        history["game_number"] = game_number
        histories.append(history)
        stacks = list(result.history["final_stacks"])
        reason = result.history["events"][-1].get("reason")
        used_all_in = any(bool(event.get("all_in")) for event in result.history["events"])
        if len(result.winners) == 1:
            winner = result.winners[0]
            pots_won[winner] += 1
            if used_all_in:
                all_ins_won[winner] += 1
            if reason == "showdown":
                showdowns_won[winner] += 1
            if reason in {"fold", "bot_forfeit"}:
                folds_forced[winner] += 1
        if 0 in stacks:
            winner = 1 if stacks[0] == 0 else 0
            return TournamentGameResult(
                game_number, winner, hand_number, (stacks[0], stacks[1]),
                (pots_won[0], pots_won[1]), (all_ins_won[0], all_ins_won[1]),
                (showdowns_won[0], showdowns_won[1]), (folds_forced[0], folds_forced[1]),
                tuple(histories),
            )
    raise RuntimeError(f"tournament game exceeded {max_hands} hands")


def play_tournament_series(
    bots: Sequence[Bot],
    *,
    seed: int,
    bot_names: tuple[str, str] = ("bot_a", "bot_b"),
    match_id: str = "series-1",
    timeout_seconds: float = 1.0,
    on_game_completed: Callable[[TournamentGameResult, tuple[int, int]], None] | None = None,
) -> TournamentSeriesResult:
    """Play independent PLHE games until one bot wins three."""
    score = [0, 0]
    games: list[TournamentGameResult] = []
    for game_number in range(1, 6):
        game = play_tournament_game(
            bots,
            game_number=game_number,
            seed=seed + (game_number - 1) * 100_000,
            match_id=match_id,
            first_dealer=(game_number - 1) % 2,
            timeout_seconds=timeout_seconds,
        )
        games.append(game)
        score[game.winner] += 1
        if on_game_completed is not None:
            on_game_completed(game, (score[0], score[1]))
        if score[game.winner] == 3:
            return TournamentSeriesResult(
                match_id, seed, bot_names, game.winner, (score[0], score[1]),
                sum(item.hands for item in games), tuple(games),
            )
    raise AssertionError("best-of-five series did not produce a winner")


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
