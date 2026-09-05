def decide(state):
    legal = state["legal_actions"]
    if "check" in legal:
        return {"action": "check"}
    return {"action": "fold"}
