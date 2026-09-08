# Training Dojo: local review

Branch: `codex/training-dojo`, based on main `2ed9676`. Not merged or published.

## Implemented

- `/training` uses the same card surface, circular portrait component, and side
  drawer styling as Rivals. Training is between My Bot and Rivals in signed-in
  desktop/mobile navigation. Existing landing page remains simple.
- Five unlocked packaged strategies in measured order: Pebble, Spark, Anchor,
  Mirage, Summit. Four existing character assets are reused; Anchor and Summit
  share the bear artwork for this first version.
- Each card opens its opponent details and an agent-ready copyable prompt.
  Technical setup stays with the coding agent.
- `train --opponent ID` runs entirely locally for those five IDs. Only public
  engine/evaluator/strategy files are copied into the starter kit.
- `train --opponent leader` preserves the existing hosted WebSocket path.
  `dojo list` adds the live leader's name/player/public Elo, but the leader does
  not appear in the Dojo or count toward completion. Missing leader data is
  explicitly unavailable, never replaced with invented standings.
- Saved training ZIPs open in the existing local viewer, with highlights and
  every retained hand. No second viewer was built.
- Versioned local progress, private authenticated account sync, repeat-safe
  writes, and account-isolated reads. Sync is explicit, not automatic.
- Agent prompt, starter README, WORKFLOWS, CLI documentation, and starter ZIP updated.

## Ratings and trust boundaries

`dojo-calibration.json` contains actual results from two independent seeded
deal sets, each 20,000 hands. Each pair of bots played ten 200-hand matches per
set. Every consecutive pair of hands swaps the bots over the same physical deal.
Ratings are logistic fits to match wins/draws, with a half-win prior, centered
at 1200. The first set supplies displayed ratings; the second verifies order.
Both produced Pebble < Spark < Anchor < Mirage < Summit with zero bot errors.
These are preliminary dojo-pool ratings, not public league Elo, and are not a
guarantee that a higher-rated strategy wins every matchup or training run.

Reproduce each report:

```sh
PYTHONPATH=server python3 qa/dojo_calibrate.py --pairs 1000 --seed 20260908
PYTHONPATH=server python3 qa/dojo_calibrate.py --pairs 1000 --seed 20261009
```

The source hash differs between the two saved reports only because the public
ID ordering was changed to match the measured progression. Strategies are the
same. The second report matches the final strategy source.

A local checkmark requires at least 200 mirrored hands, positive net chips,
and zero bot errors. Local files and claims can be edited, so synced checkmarks
are explicitly **self-reported local practice**, not verified achievements.
The API validates shape, bounds, opponent/version, owner, and idempotency, but
does not attest to local execution. Nothing changes public Elo or league results.
Opponent-version changes reset current-version progress without deleting history.

## Verification

- Full `npm run qa`: website build/render/navigation tests, lint, 236 Python
  server tests, 66 CLI tests, starter packaging, and real WebSocket-to-local-recap
  smoke passed. The final targeted API suite passed 20 tests, including an
  additional live-leader metadata/privacy test added after the full run.
- New API tests cover authentication, account isolation, repeat sync,
  conflicting duplicate IDs, retired versions, malformed data, incomplete runs,
  errors/draws/losses, and unchanged leaderboard results.
- `qa/dojo_smoke.py` extracts the actual starter ZIP, runs all five opponents
  against an unreachable API, runs 200 mirrored hands against Pebble, opens the
  standalone viewer, loads hand 200, and syncs the result twice to an isolated API.
  This is also wired into `npm run qa` as its postqa check.
- Actual Chrome inspection: desktop/mobile cards and drawer, copied prompt,
  keyboard Escape/focus return, mobile nav, Leaderboard navigation, signed-in
  progress showing 1/5 and suggested next, and local viewer hand 200.
- Mobile viewport 390 x 844, no horizontal overflow. Viewport restored afterward.
- Standalone `tsc --noEmit` still reports the existing missing `Fetcher` and
  `D1Database` ambient types in `worker/index.ts`. That file and tsconfig are
  unchanged from main. No dojo TypeScript diagnostics were reported. The
  application build and lint pass; this legacy worker type setup is not changed
  as part of the dojo feature.

Preview uses a dedicated loopback API on 8128 and web server on 3028. Build with
`ALPHA_POKER_API_URL=http://127.0.0.1:8128/v1` before starting: vinext embeds that
URL during the build. Do not use the container API hostname for a local build.

No production credentials, production SQLite, or deployment state were used.
Google sign-in is concurrently developed in the separate Poker Site task.
Rebase and rerun QA against its merged auth changes before a future release.
