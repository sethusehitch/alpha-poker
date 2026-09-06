# Alpha Poker Rivals MVP release report

Date: 2026-09-05
Branch: `codex/rivals-mvp`
Environment: isolated local Docker Compose stack at `127.0.0.1:18081`

## Scope

This release adds one authenticated Rivals workspace, direct asynchronous
challenges, challenge notifications, direct-only head-to-head history, match
recaps and hand replays, plus agent-friendly CLI commands. Direct challenges
are play-money-only, unranked, and do not change public Elo. The public landing
page remains simple.

Feature requests and Contribute are visible in navigation only after login and
are grouped under a separate Community menu. Rivals and Leaderboard remain the
core game navigation.

## Automated verification

- Production frontend build passed.
- Frontend rendered, community, Rivals, header, hand-replay, and container
  contract tests passed.
- ESLint passed.
- Server suite passed: 119 tests.
- CLI suite passed: 32 tests.
- Python compileall passed.
- The starter ZIP was regenerated from the verified CLI and documentation.
- `git diff --check` passed.
- A repository scan found no disposable QA credentials or bearer tokens.

The build reports only the pre-existing Vite native config-loader migration
warning.

## Container and protocol verification

- The isolated Caddy, web, and API containers reached healthy status.
- Existing SQLite-backed rival state survived API and web rebuilds.
- The HTTP smoke test passed through Caddy.
- The Training WebSocket smoke test passed through Caddy.
- A completed challenge remained available after an API container restart.
- Challenge lifecycle, duplicate-open protection, idempotency, serialized work,
  restart recovery, retention, participant-only artifacts, and unchanged Elo
  are covered by server tests.

## Independent black-box acceptance

Successive independent agents received no source context and tested only the
running site, downloaded starter kit, and public CLI surface. Each failed build
was fixed, rebuilt, and handed to a clean-slate pass.

The first pass completed a real 200-hand challenge and found stale private
notification state after logout, clipped mobile navigation, ambiguous result
links, UTC-facing dates, feedback overlap, and implementation-facing replay
labels. Those defects were reproduced and fixed.

The second pass completed another challenge through the website and downloaded
CLI. It verified 200 hands, 100 mirrored deal pairs, unranked status, unchanged
1,200 Elo ratings, participant notifications, exact recap links, replay Back
behavior, and immediate logout privacy. It found an overlay collision,
indistinguishable repeated notifications, and incorrect copy for tied focused
hands. Those defects were reproduced and fixed.

Later passes found and verified fixes for asynchronous account-state races,
overlay ownership, exact replay return links, and a retained search filter
during rapid account switching.

The final unchanged-build pass returned **SHIP**. It verified both directions
of rapid account switching with blank per-account search state, exact recap to
hand replay to recap restoration, mutually exclusive overlays, local
notification timestamps and keyboard focus, tied-hand copy, signed-out privacy,
the separate signed-in Community menu, the two-line mobile hero, and existing
200-hand unranked challenge evidence with unchanged Elo.

## Release boundary

This report authorizes a merge to `main` after the final clean-slate verdict and
CI are green. It does not authorize a production deployment. Production remains
unchanged until explicitly requested.
