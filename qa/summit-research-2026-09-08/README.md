# Summit v2: complete and verified locally

Selected policy: research v27, exposed as opponent version `summit-v2`.
The installed source exactly matches the frozen candidate, SHA256
`cda885295952950167ab0ae770a5611598f598b56c0d7a776e659515c7f0fb56`.
No deployment or public Elo changes are included.

## Acceptance evidence

- Two disjoint fresh Mirage batches: 18/20 wins in each best-of-five tournament batch.
- Fresh lower-opponent batches: Pebble 20/20, Spark 20/20, Anchor 19/20, old Summit 18/20.
- Matched reference pool: 83/110 series versus 70/110 for the original range prototype.
  No individual drop exceeded one win out of ten. Zero bot errors.
- 996 legal-state/runtime checks, separate-instance audit, and short-stack aggression check passed.
- 564 first-four-opponent decisions exactly matched original commit 606e861.
- Local fixed-stack mirrored NLHE validation: +65,368 play chips versus Mirage
  and +58,387 versus old Summit, 2,000 hands each, zero errors. This comparison
  used the prior local runner's mirrored memory convention; the rating run below
  uses the new isolated legs.

`ACCEPTANCE.json` and `accepted-*.json` retain the detailed results and hashes.
All failed candidates and failed acceptance batches remain in `CHECKPOINT.json`.
The complete raw evidence location is also recorded there.

## Ratings

`../dojo-calibration.json` is the current reproducible 40,000-hand rating report.
`../dojo-calibration-v1.json` preserves the original report. Reproduce the new
method with `PYTHONPATH=server python3 qa/dojo_calibrate_v2.py --out NEW_DIRECTORY`.

Each set contains ten 200-hand fixed-stack NLHE matches per pairing. Duplicate
legs have separate memory, and strategy randomness is independent of deal seeds.
Ratings fit match wins/draws with a half-win prior, centered at 1200.

| Opponent | Displayed calibration | Independent validation |
| --- | ---: | ---: |
| Pebble | 692 | 637 |
| Spark | 1042 | 971 |
| Anchor | 1219 | 1170 |
| Mirage | 1452 | 1453 |
| Summit | 1595 | 1769 |

Both sets preserve the intended order with zero errors. Values remain provisional
and pool-relative; the variation between sets illustrates uncertainty. They are
not public-league Elo. Tournament acceptance is a separate format and does not
establish a universal 90% win probability or a student learning-time guarantee.

## Strategy and research

The accepted policy samples opponent holdings, updates their likelihood from
public actions, compares several legal bet sizes, and uses mild concave chip
utility to account for the value of future opportunities. This is an approximate
adaptive policy, not a GTO solver. Its utility calculation approximates ties via
equity and does not solve the entire future tournament.

The renewed source review is in `RESEARCH.md`. Slumbot2019, PokerKit, HoldemLab,
and Texas-Holdem-AI were reviewed alongside earlier Treys/OpenSpiel/PokerRL/RLCard
research. No verified drop-in pretrained policy met this contract. The earlier
Treys-backed policy regressed broadly; it was not selected solely because it
used an external evaluator. No new external strategy code was imported.

Versions v16-v24 explored action EV, sampling precision, opponent-style inference,
re-raise response, and equity realization. V25-v27 tested a declared risk-utility
grid. V28-v29 explored synthetic-deal multi-street simulation with the public
AlphaPoker state machine; those prototypes were not selected. V30-v31 explored
stack-dependent risk. Development schedules never counted as fresh acceptance.

## Integration

Only Summit's policy changes. Each packaged instance has its own memory.
Per-opponent versioning retires old Summit wins from current progress while
preserving history and the other four opponents' wins. Both duplicate copies
now run in separate student processes/opponent instances. Local artifacts record
independent strategy randomness for reproduction. The 200-hand positive-result
checkmark remains self-reported practice and does not change public Elo.

The branch includes origin/main through 8f0b017 and preserves Google sign-in.
Server, generated CLI assets, and the downloadable starter share the same policy.
Full `npm run qa` passed: website build and UI checks, lint, 251 server tests,
71 CLI tests, extracted-starter offline training against all five opponents,
200-hand recap loading, repeat-safe account sync, and standalone viewer checks.
The local training route also returned HTTP 200. See `FINAL_QA.json` and
`FINAL_QA.txt`. This local completion is not a production deployment.
