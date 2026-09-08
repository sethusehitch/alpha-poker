"""Public, locally packaged practice opponents. Never imports submitted bots."""
import json
from pathlib import Path
import random
from .evaluator import evaluate, RANKS, SUITS

VERSION = "dojo-v1"
IDS = ("pebble", "spark", "anchor", "mirage", "summit")

def catalog():
    return json.loads(Path(__file__).with_name("dojo_catalog.json").read_text())


def equity(state, samples):
    hole, board = state["hole_cards"], state["community_cards"]
    rng = random.Random(state["bot_random_seed"] + len(state["action_history"]) * 7919)
    deck = [r + s for r in RANKS for s in SUITS if r + s not in hole + board]
    score = 0
    for _ in range(samples):
        draw = rng.sample(deck, 7 - len(board))
        complete = board + draw[2:]
        ours, theirs = evaluate(hole + complete), evaluate(draw[:2] + complete)
        score += (ours > theirs) + .5 * (ours == theirs)
    return score / samples


class PackagedBot:
    # Trusted bounded pure Python opponent; student bots still use killable IPC.
    _alpha_poker_enforces_timeout = True

    def __init__(self, opponent):
        if opponent not in IDS:
            raise ValueError("Unknown dojo opponent")
        self.opponent = opponent

    def decide(self, state):
        legal = state["legal_actions"]
        check = {"action": "check" if "check" in legal else "fold"}
        call = {"action": "check" if "check" in legal else "call"}
        def raise_to(fraction):
            if "raise" not in legal:
                return call
            low, high = state["min_raise_to"], state["max_raise_to"]
            return {"action": "raise", "amount": min(high, max(low, int(low + (high - low) * fraction)))}
        if self.opponent == "pebble":
            return check
        ranks = sorted([RANKS.index(c[0]) + 2 for c in state["hole_cards"]], reverse=True)
        pair = ranks[0] == ranks[1]
        preflop = state["street"] == "preflop"
        if self.opponent == "anchor":
            strong = (pair or ranks[1] >= 11) if preflop else evaluate(state["hole_cards"] + state["community_cards"])[0] >= 1
            return call if strong else check
        if self.opponent == "spark":
            rng = random.Random(state["bot_random_seed"] + len(state["action_history"]))
            if rng.random() < .5:
                return raise_to(.12)
            return call
        strength = equity(state, 12 if self.opponent == "mirage" else 64)
        price = state["to_call"] / max(1, state["pot"] + state["to_call"])
        rng = random.Random(state["bot_random_seed"] + len(state["action_history"]) * 17)
        bluff = rng.random() < (.07 if self.opponent == "mirage" else .025)
        if strength > .7 or (bluff and state["to_call"] == 0):
            return raise_to(.18)
        if strength > price + .16:
            return call
        return check
