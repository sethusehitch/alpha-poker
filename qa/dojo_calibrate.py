"""Reproducible dojo-only rating benchmark. Never uses uploaded submissions.

PYTHONPATH=server python3 qa/dojo_calibrate.py --pairs 1000 --seed 20260908
Each matchup uses paired identical deals with seats swapped. Ratings are fitted
to 200-hand match wins/draws with a half-win prior, centered at 1200
(not public Elo). Each matchup is a sequence of 100-pair matches.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
from alpha_poker.dojo import IDS, VERSION, PackagedBot
from alpha_poker.engine import play_hand, shuffled_deal


def benchmark(pairs, seed):
    results = []
    for a, b in itertools.combinations(IDS, 2):
        wins = losses = ties = net = errors = 0
        batch_net = 0
        for pair in range(pairs):
            pair_net = 0
            for seat in (0, 1):
                bots = (PackagedBot(a), PackagedBot(b)) if seat == 0 else (PackagedBot(b), PackagedBot(a))
                result = play_hand(bots, seed=seed+pair, deal=shuffled_deal(seed+pair),
                    hand_id=f"cal_{a}_{b}_{pair}_{seat}", dealer=0,
                    starting_stack=2000, small_blind=10, big_blind=20,
                    bot_random_seeds=(seed+pair*2, seed+pair*2+1))
                pair_net += result.profits[seat]
                errors += sum(e.get("type") == "bot_error" for e in result.history["events"])
            batch_net += pair_net
            if (pair + 1) % 100 == 0:
                wins += batch_net > 0
                losses += batch_net < 0
                ties += batch_net == 0
                batch_net = 0
            net += pair_net
        row = dict(a=a, b=b, wins=wins, losses=losses, ties=ties, net_chips=net, errors=errors)
        results.append(row)
        print(json.dumps(row), flush=True)
    ratings = {bot: 1200.0 for bot in IDS}
    for _ in range(2000):
        delta = {bot: 0.0 for bot in IDS}
        for row in results:
            a, b = row["a"], row["b"]
            observed = (row["wins"] + row["ties"]*.5 + .5) / (pairs//100+1)
            expected = 1/(1+10**((ratings[b]-ratings[a])/400))
            delta[a] += observed-expected
            delta[b] -= observed-expected
        for bot in IDS:
            ratings[bot] += 4*delta[bot]
    source = Path(__file__).resolve().parents[1]/"server/alpha_poker/dojo.py"
    report = dict(version=VERSION, seed=seed, pairs_per_matchup=pairs,
        total_hands=pairs*20, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        ratings={bot: round(ratings[bot]) for bot in IDS}, matchups=results)
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260908)
    args = parser.parse_args()
    if args.pairs < 100 or args.pairs % 100:
        parser.error("--pairs must be a positive multiple of 100 (200-hand matches)")
    benchmark(args.pairs, args.seed)
