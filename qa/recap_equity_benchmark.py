"""Bounded exact-preflop benchmark and five-hand cold/warm recap estimate.

PYTHONPATH=server server/.venv/bin/python qa/recap_equity_benchmark.py
Full preflop has 1,712,304 boards. Time an exact 10,000-board prefix and report
the projection, rather than blocking a development session for several minutes.
"""
from itertools import combinations, islice
from math import comb
from time import perf_counter
from alpha_poker.evaluator import evaluate
from alpha_poker_api.recap_equity import DECK, _calculate, showdown_equity

holes = [["As", "Kd"], ["9s", "9h"]]
remaining = [c for c in DECK if c not in holes[0] + holes[1]]
start = perf_counter()
for board in islice(combinations(remaining, 5), 10000):
    for hand in holes:
        evaluate(hand + list(board))
elapsed = perf_counter() - start
print(f"Exact prefix: 10,000 boards in {elapsed:.3f}s; {comb(48, 5):,} total boards; projected exact preflop {elapsed * comb(48, 5) / 10000:.1f}s")
_calculate.cache_clear()
start = perf_counter()
estimate = showdown_equity(holes, [])
print(f"Fixed-seed {estimate['trials']:,}-board estimate: {perf_counter() - start:.3f}s, {estimate['percentages']}")
for board in (["Ts", "Jd", "Qc"], ["Ts", "Jd", "Qc", "Kh"], ["Ts", "Jd", "Qc", "Kh", "2c"]):
    start = perf_counter()
    value = showdown_equity(holes, board)
    print(f"{len(board)}-card board: exact {value['trials']} runouts in {perf_counter() - start:.3f}s, {value['percentages']}")

pairs = [[["As","Kd"],["9s","9h"]], [["Ah","Ad"],["Kc","Ks"]], [["7s","8s"],["Tc","Td"]],
         [["2h","2d"],["Qc","Js"]], [["Ac","Qd"],["Kh","Jh"]]]
_calculate.cache_clear()
cache = {}
start = perf_counter()
for pair in pairs:
    board = [c for c in DECK if c not in pair[0] + pair[1]][:5]
    for count in (0, 3, 4, 5):
        showdown_equity(pair, board[:count], cache)
print(f"Five distinct cold hands (all streets): {perf_counter() - start:.3f}s; local target <=2.5s")
