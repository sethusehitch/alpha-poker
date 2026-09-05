def decide(state):
    legal = state["legal_actions"]
    if "raise" in legal and state["hand_number"] % 3 == 0:
        return {"action": "raise", "amount": state["min_raise_to"]}
    if "check" in legal:
        return {"action": "check"}
    if "call" in legal:
        return {"action": "call"}
    return {"action": "fold"}
