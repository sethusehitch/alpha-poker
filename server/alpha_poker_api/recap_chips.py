"""Pure, additive street ledger over normalized replay snapshots.

The old step.pot stays the total (gathered + wagers). New clients render only
table_chips.gathered_pot centrally. Unknown payments are never reconstructed
from raise targets or a total. A retained total can restore the gathered pot
only at a boundary where every outstanding wager has been cleared.
"""


def street_wagers(steps: list[dict], *, complete_start: bool) -> list[dict]:
    gathered = 0 if complete_start else None
    wagers = [0, 0] if complete_start else [None, None]
    current_street = "preflop"
    previous = None
    seen_payment = False
    result = []

    def snapshot(before, gathered_before, phase="idle", sweep=None):
        return {"version": "street-wagers-v1", "phase": phase,
                "gathered_before": gathered_before, "gathered_pot": gathered,
                "wagers_before": list(before), "wagers": list(wagers),
                "sweep": list(sweep) if sweep is not None else [0, 0]}

    for source in steps:
        step = dict(source)
        street = step["street"]
        boundary = street != current_street and street in {"preflop", "flop", "turn", "river", "showdown", "result"}
        if boundary:
            if previous and seen_payment and any(n is None or n > 0 for n in wagers):
                before, gathered_before = list(wagers), gathered
                # The prior snapshot is before any new-street payment. A final
                # retained pot may restore an unknown total, but not a payment.
                total = previous["pot"]
                if total is None and street == "result":
                    total = step["pot"]
                if total is not None:
                    gathered = total
                elif gathered is not None and all(n is not None for n in wagers):
                    gathered += sum(wagers)
                else:
                    gathered = None
                wagers = [0, 0]
                copy = f"Gathering {current_street} wagers"
                sweep = {**previous, "actor_seat": None, "action_kind": None, "committed_amount": None,
                         "summary": copy, "action_label": copy, "pot_before": previous["pot"],
                         "table_chips": snapshot(before, gathered_before, "sweep", before)}
                result.append(sweep)
            current_street = street
        before, gathered_before = list(wagers), gathered
        kind, seat, paid = step.get("action_kind"), step.get("actor_seat"), step.get("committed_amount")
        payment = kind in {"small_blind", "big_blind", "bet", "call", "raise", "all_in"} or (paid is not None and paid > 0)
        if payment:
            seen_payment = True
            if seat in (0, 1):
                wagers[seat] = wagers[seat] + paid if wagers[seat] is not None and paid is not None else None
            else:
                wagers = [None, None]
        if street == "result":
            # Final pot award is an authoritative end snapshot, not live wagers.
            gathered, wagers = step["pot"], [0, 0]
        step["table_chips"] = snapshot(before, gathered_before, "payment" if payment else "idle")
        result.append(step)
        previous = step
    return result
