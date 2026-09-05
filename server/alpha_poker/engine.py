"""Heads-up no-limit Hold'em hand state machine."""

from __future__ import annotations

import copy
import json
import random
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .evaluator import RANKS, SUITS, describe, evaluate, validate_card

Bot = Any
SCHEMA_VERSION = "2026-09-01"
MAX_ACTION_BYTES = 4_096


class BotDecisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class HandResult:
    hand_id: str
    seed: int
    dealer: int
    winners: tuple[int, ...]
    profits: tuple[int, int]
    history: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.history)


def shuffled_deal(seed: int) -> dict[str, Any]:
    deck = [rank + suit for rank in RANKS for suit in SUITS]
    random.Random(seed).shuffle(deck)
    # Deal one card at a time, then burn before flop, turn, and river.
    holes = [[], []]
    for _ in range(2):
        for seat in range(2):
            holes[seat].append(deck.pop())
    deck.pop()
    flop = [deck.pop(), deck.pop(), deck.pop()]
    deck.pop()
    turn = deck.pop()
    deck.pop()
    river = deck.pop()
    return {"holes": holes, "board": flop + [turn, river]}


class HoldemHand:
    """Mutable hand state. Bots only receive copies returned by ``bot_state``."""

    streets = ("preflop", "flop", "turn", "river")

    def __init__(
        self,
        *,
        hand_id: str,
        seed: int,
        match_id: str = "local-match",
        hand_number: int = 1,
        dealer: int = 0,
        starting_stack: int = 10_000,
        small_blind: int = 50,
        big_blind: int = 100,
        decision_deadline_ms: int = 1_000,
        bot_random_seeds: tuple[int, int] | None = None,
        deal: Mapping[str, Any] | None = None,
    ) -> None:
        if starting_stack <= big_blind or not 0 < small_blind < big_blind:
            raise ValueError("invalid stack or blinds")
        self.hand_id, self.seed, self.dealer = hand_id, seed, dealer
        self.match_id, self.hand_number = match_id, hand_number
        self.decision_deadline_ms = decision_deadline_ms
        self.bot_random_seeds = bot_random_seeds or (seed * 2, seed * 2 + 1)
        self.starting_stack = starting_stack
        self.small_blind, self.big_blind = small_blind, big_blind
        dealt = copy.deepcopy(dict(deal)) if deal is not None else shuffled_deal(seed)
        self.holes = [list(cards) for cards in dealt["holes"]]
        self.full_board = list(dealt["board"])
        all_cards = self.holes[0] + self.holes[1] + self.full_board
        if len(self.holes[0]) != 2 or len(self.holes[1]) != 2 or len(self.full_board) != 5:
            raise ValueError("a deal requires two hole cards per seat and five board cards")
        if len(set(all_cards)) != 9:
            raise ValueError("deal cards must be unique")
        for card in all_cards:
            validate_card(card)

        self.stacks = [starting_stack, starting_stack]
        self.total_contrib = [0, 0]
        self.street_contrib = [0, 0]
        self.street_index = 0
        self.board: list[str] = []
        self.folded: int | None = None
        self.finished = False
        self.winners: tuple[int, ...] = ()
        self.events: list[dict[str, Any]] = []
        self.acted: set[int] = set()
        self.last_full_raise = big_blind
        self.current_bet = 0

        self._post_blind(dealer, small_blind, "small_blind")
        self._post_blind(1 - dealer, big_blind, "big_blind")
        self.current_bet = big_blind
        self.actor = dealer

    @property
    def street(self) -> str:
        return self.streets[self.street_index]

    @property
    def pot(self) -> int:
        return sum(self.total_contrib)

    def _post_blind(self, seat: int, amount: int, kind: str) -> None:
        paid = min(amount, self.stacks[seat])
        self.stacks[seat] -= paid
        self.street_contrib[seat] += paid
        self.total_contrib[seat] += paid
        self.events.append({"type": kind, "seat": seat, "amount": paid})

    def legal_actions(self, seat: int | None = None) -> list[dict[str, Any]]:
        seat = self.actor if seat is None else seat
        if self.finished or seat != self.actor:
            return []
        other = 1 - seat
        to_call = self.current_bet - self.street_contrib[seat]
        actions: list[dict[str, Any]] = [{"type": "fold"}]
        if to_call == 0:
            actions.append({"type": "check"})
        else:
            actions.append({"type": "call", "amount": min(to_call, self.stacks[seat])})
        effective_to = min(
            self.street_contrib[seat] + self.stacks[seat],
            self.street_contrib[other] + self.stacks[other],
        )
        min_to = self.current_bet + self.last_full_raise
        if effective_to >= min_to:
            actions.append(
                {
                    "type": "raise",
                    "min_to": min_to,
                    "max_to": effective_to,
                }
            )
        if effective_to > self.street_contrib[seat]:
            actions.append({"type": "all_in", "to": effective_to})
        return actions

    def bot_state(self, seat: int) -> dict[str, Any]:
        internal_legal = self.legal_actions(seat)
        by_name = {item["type"]: item for item in internal_legal}
        # Folding with nothing to call remains an internal escape hatch for a bot
        # failure, but is not offered as a strategic action in the public API.
        legal_names = [
            item["type"]
            for item in internal_legal
            if not (item["type"] == "fold" and "check" in by_name)
        ]
        raise_bounds = by_name.get("raise")
        return {
            "schema_version": SCHEMA_VERSION,
            "match_id": self.match_id,
            "hand_id": self.hand_id,
            "hand_number": self.hand_number,
            "seat": seat,
            "button_seat": self.dealer,
            "street": self.street,
            "hole_cards": list(self.holes[seat]),
            "community_cards": list(self.board),
            "pot": self.pot,
            "stacks": {str(i): amount for i, amount in enumerate(self.stacks)},
            "committed": {str(i): amount for i, amount in enumerate(self.street_contrib)},
            "to_call": self.current_bet - self.street_contrib[seat],
            "min_raise_to": raise_bounds["min_to"] if raise_bounds else None,
            "max_raise_to": raise_bounds["max_to"] if raise_bounds else None,
            "legal_actions": legal_names,
            "action_history": copy.deepcopy(self.events),
            "decision_deadline_ms": self.decision_deadline_ms,
            "bot_random_seed": self.bot_random_seeds[seat],
        }

    def act(self, action: Mapping[str, Any]) -> None:
        if self.finished:
            raise ValueError("hand is finished")
        seat, other = self.actor, 1 - self.actor
        kind = action.get("type")
        legal = {item["type"]: item for item in self.legal_actions()}
        if kind not in legal:
            raise ValueError(f"illegal action {kind!r}")
        to_call = self.current_bet - self.street_contrib[seat]

        if kind == "fold":
            self.folded = seat
            self.events.append({"type": "action", "seat": seat, "action": "fold", "street": self.street})
            self._award((other,), "fold")
            return
        if kind == "check":
            paid, raise_size = 0, 0
        elif kind == "call":
            paid, raise_size = min(to_call, self.stacks[seat]), 0
        else:
            target = legal[kind].get("to") if kind == "all_in" else action.get("to")
            if not isinstance(target, int):
                raise ValueError("raise action requires integer 'to'")
            bounds = legal.get("raise")
            effective_max = bounds["max_to"] if bounds else legal["all_in"]["to"]
            if target > effective_max or target <= self.street_contrib[seat]:
                raise ValueError("raise is outside the legal range")
            if kind == "raise" and target < bounds["min_to"]:
                raise ValueError("raise is below the minimum")
            paid = target - self.street_contrib[seat]
            raise_size = max(0, target - self.current_bet)

        self.stacks[seat] -= paid
        self.street_contrib[seat] += paid
        self.total_contrib[seat] += paid
        if raise_size:
            previous_raise = self.last_full_raise
            self.current_bet = self.street_contrib[seat]
            if raise_size >= previous_raise:
                self.last_full_raise = raise_size
                self.acted = {seat}
            else:
                self.acted.add(seat)
        else:
            self.acted.add(seat)
        self.events.append(
            {
                "type": "action",
                "seat": seat,
                "action": kind,
                "amount": paid,
                "to": self.street_contrib[seat],
                "street": self.street,
                "pot_after": self.pot,
            }
        )

        contributions_equal = self.street_contrib[0] == self.street_contrib[1]
        someone_all_in = 0 in self.stacks
        round_complete = contributions_equal and (len(self.acted) == 2 or someone_all_in)
        if round_complete:
            self._advance_or_showdown()
        else:
            self.actor = other

    def forfeit(self, seat: int) -> None:
        """End the hand after a bot failure, independent of strategic actions."""
        if self.finished or seat != self.actor:
            raise ValueError("only the acting seat can forfeit an active hand")
        self.folded = seat
        self.events.append({"type": "forfeit", "seat": seat, "street": self.street})
        self._award((1 - seat,), "bot_forfeit")

    def _advance_or_showdown(self) -> None:
        if self.street_index == 3 or 0 in self.stacks:
            self.board = list(self.full_board)
            self.events.append({"type": "board", "street": "showdown", "cards": list(self.board)})
            ranks = [evaluate(self.holes[seat] + self.board) for seat in range(2)]
            self.events.append(
                {
                    "type": "showdown",
                    "hands": [
                        {
                            "seat": seat,
                            "hole_cards": list(self.holes[seat]),
                            "rank": list(ranks[seat]),
                            "category": describe(ranks[seat]),
                        }
                        for seat in range(2)
                    ],
                }
            )
            outcome = (ranks[0] > ranks[1]) - (ranks[0] < ranks[1])
            self._award((0,) if outcome > 0 else (1,) if outcome < 0 else (0, 1), "showdown")
            return
        self.street_index += 1
        count = (3, 4, 5)[self.street_index - 1]
        self.board = self.full_board[:count]
        self.street_contrib = [0, 0]
        self.current_bet = 0
        self.last_full_raise = self.big_blind
        self.acted.clear()
        self.actor = 1 - self.dealer
        self.events.append({"type": "board", "street": self.street, "cards": list(self.board)})

    def _award(self, winners: tuple[int, ...], reason: str) -> None:
        pot = self.pot
        share, odd = divmod(pot, len(winners))
        for winner in winners:
            self.stacks[winner] += share
        if odd:
            odd_recipient = next(seat for seat in (1 - self.dealer, self.dealer) if seat in winners)
            self.stacks[odd_recipient] += odd
        self.winners = winners
        self.finished = True
        self.events.append({"type": "result", "winners": list(winners), "pot": pot, "reason": reason})

    def result(self) -> HandResult:
        if not self.finished:
            raise ValueError("hand is not finished")
        profits = (self.stacks[0] - self.starting_stack, self.stacks[1] - self.starting_stack)
        history = {
            "schema_version": "1.0",
            "hand_id": self.hand_id,
            "match_id": self.match_id,
            "hand_number": self.hand_number,
            "seed": self.seed,
            "game": "NLHE",
            "currency": "play_chips",
            "dealer": self.dealer,
            "blinds": {"small": self.small_blind, "big": self.big_blind},
            "starting_stacks": [self.starting_stack, self.starting_stack],
            "hole_cards": copy.deepcopy(self.holes),
            "board": list(self.board),
            "pot": self.pot,
            "events": copy.deepcopy(self.events),
            "winners": list(self.winners),
            "final_stacks": list(self.stacks),
            "profits": list(profits),
        }
        return HandResult(self.hand_id, self.seed, self.dealer, self.winners, profits, history)


def _decide(bot: Bot, state: dict[str, Any], timeout_seconds: float) -> Mapping[str, Any]:
    function: Callable[[dict[str, Any]], Any] = getattr(bot, "decide", bot)
    if not callable(function):
        raise BotDecisionError("bot must be callable or expose decide(state)")
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="alpha-poker-bot")
    future = executor.submit(function, copy.deepcopy(state))
    try:
        answer = future.result(timeout=timeout_seconds)
    except FutureTimeout as exc:
        future.cancel()
        raise BotDecisionError("decision timed out") from exc
    except Exception as exc:
        raise BotDecisionError(f"bot raised {type(exc).__name__}: {exc}") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    if not isinstance(answer, Mapping):
        raise BotDecisionError("decision must be an object")
    try:
        encoded = json.dumps(answer, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise BotDecisionError(f"decision is not JSON-compatible: {exc}") from exc
    if len(encoded) > MAX_ACTION_BYTES:
        raise BotDecisionError("decision exceeds 4 KB")
    name = answer.get("action")
    if name not in state["legal_actions"]:
        raise BotDecisionError(f"action {name!r} is not legal in this state")
    allowed_fields = {"action", "amount"} if name == "raise" else {"action"}
    extra = set(answer) - allowed_fields
    if extra:
        raise BotDecisionError(f"unexpected action fields: {', '.join(sorted(extra))}")
    if name == "raise":
        amount = answer.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise BotDecisionError("raise amount must be an integer")
        if not state["min_raise_to"] <= amount <= state["max_raise_to"]:
            raise BotDecisionError("raise amount is outside the legal range")
        return {"type": "raise", "to": amount}
    if "amount" in answer:
        raise BotDecisionError("amount is only valid for raise")
    return {"type": name}


def play_hand(
    bots: Sequence[Bot],
    *,
    seed: int,
    hand_id: str = "hand-1",
    match_id: str = "local-match",
    hand_number: int = 1,
    dealer: int = 0,
    starting_stack: int = 10_000,
    small_blind: int = 50,
    big_blind: int = 100,
    timeout_seconds: float = 1.0,
    bot_random_seeds: tuple[int, int] | None = None,
    deal: Mapping[str, Any] | None = None,
) -> HandResult:
    if len(bots) != 2:
        raise ValueError("heads-up play requires exactly two bots")
    hand = HoldemHand(
        hand_id=hand_id,
        seed=seed,
        match_id=match_id,
        hand_number=hand_number,
        dealer=dealer,
        starting_stack=starting_stack,
        small_blind=small_blind,
        big_blind=big_blind,
        decision_deadline_ms=max(1, round(timeout_seconds * 1_000)),
        bot_random_seeds=bot_random_seeds,
        deal=deal,
    )
    while not hand.finished:
        seat = hand.actor
        state = hand.bot_state(seat)
        try:
            action = _decide(bots[seat], state, timeout_seconds)
            hand.act(action)
        except (BotDecisionError, ValueError) as exc:
            hand.events.append(
                {
                    "type": "bot_error",
                    "seat": seat,
                    "street": hand.street,
                    "error": str(exc),
                    "fallback": "forfeit",
                    "elapsed_ms_upper_bound": round(timeout_seconds * 1000),
                }
            )
            hand.forfeit(seat)
    return hand.result()
