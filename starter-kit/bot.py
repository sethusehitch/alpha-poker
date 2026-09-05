"""A deliberately simple starting strategy for Alpha Poker.

Replace the body of decide() with your strategy. Use only the Python standard
library and do not perform network requests, start subprocesses, or write files.
"""


def decide(state: dict) -> dict:
    """Return one legal action for an authoritative Alpha Poker state."""
    legal = state["legal_actions"]
    hole_cards = state.get("hole_cards", [])
    ranks = {card[0] for card in hole_cards}
    premium_pair = len(ranks) == 1 and bool(ranks & set("AKQJ"))

    if premium_pair and "raise" in legal:
        minimum = state.get("min_raise_to")
        maximum = state.get("max_raise_to")
        if isinstance(minimum, int) and isinstance(maximum, int):
            return {"action": "raise", "amount": min(maximum, minimum * 2)}
    if "check" in legal:
        return {"action": "check"}
    if "call" in legal:
        return {"action": "call"}
    return {"action": "fold"}
