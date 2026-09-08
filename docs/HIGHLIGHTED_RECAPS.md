# Highlighted hand recaps

The Python API is the single source of selection, poker result descriptions,
visibility, chip accounting, and action-step state. The browser and CLI consume
the same versioned `recap-v1` payload. Playback never executes a bot.

## Routes and discovery

- `GET /v1/challenges/{challenge_id}/recap`: completed direct challenges only;
  authenticates a participant before loading retained evidence. Preserves the
  existing `challenge`, `matchup`, `best_hands`, and `artifacts_url` fields.
- `GET /v1/runs/{run_id}/matchups/{matchup_id}/recap`: one completed pairing;
  uses existing official/public versus direct/participant run authorization.
  A direct run returns direct challenge context, including its canonical URL.
- `/recaps/challenges/{challenge_id}` and
  `/recaps/runs/{run_id}/matches/{matchup_id}` render the same React component.
  Optional `?hand={hand_id}` selects a retained highlight. Unknown or unselected
  hand IDs fall back to the first highlight.

Challenge rows/history, completion notifications, the existing recap drawer,
and focused-hand pages link to the new recap. The leaderboard expands pairing
links for its exact displayed run. CLI discovery and open/print commands are
documented in [the CLI guide](../cli/README.md).

## Selection and accounting

`server/alpha_poker_api/recaps.py` orders hands by hand number and stable ID.
Candidates are prioritized as largest absolute **net** hand profit, greatest
deficit recovered to a tie or lead, first lead reversal, opening/early scoring,
and final lead change or scoring hand. One hand can carry multiple labels.
Duplicates are removed, remaining slots use strong retained hands, and the
result is displayed chronologically with at most five distinct hands. Equal
scores use the earliest hand. Tied matches, fewer than five hands, and missing
records are valid results.

Lead and comeback labels require all expected hands and known zero-sum profit
pairs. Partial or incomplete evidence receives retained-hand labels rather
than a fabricated match-wide narrative. The largest swing is net profit, not
the gross pot: a 1,680-chip pot with 840 contributed per player produces an
840-chip net win. Stacks reset every hand. Mirrored `seat_to_bot` mappings are
resolved before accumulating the matchup's score.

Both run ID and player pair are filtered in SQL, then the record's exact match
ID is verified. Legacy records without a match ID are eligible only if their
pair is unique within the run. Records are streamed in one read snapshot;
only selection statistics and the final five full replays are retained in
memory. No database migration is required.

## Visibility and playback

The API strips unrevealed opponents' cards. A participant can see their own
cards throughout; other cards appear only at a recorded showdown. Spectators
of official matches see only shown cards. Detailed bot-error strings are not
included. Poker categories are evaluated from actual revealed cards and board;
folds and bot forfeits have explicit descriptions. Missing values remain
unavailable rather than being presented as zero. Responses are `private,
no-store`, and the browser discards cached recap state when the account changes.

Previous/Next choose highlights. Play/Pause steps through recorded events.
The expandable action list selects an exact event, and every hand initially
opens at its final result. The pot at a result is labeled **Pot awarded**, while
player stacks show their post-award balances.

## Local QA

`qa/recap_fixture.py` creates a new database only beneath `.wrangler/recap-qa`
and refuses to overwrite one. It generates eight real engine hands, including
a tie and mirrored seats. Its published local-only QA password must never be
used outside this fixture. Do not expose the fixture API beyond loopback.

Run the API on port 8012 with `ALPHA_POKER_DATA_DIR=.wrangler/recap-qa`,
`ALPHA_POKER_SEED=false`, `ALPHA_POKER_AUTO_RUN=false`, and
`ALPHA_POKER_AUTH_REQUIRED=true`. For the Cloudflare-backed local web runtime,
set `ALPHA_POKER_API_URL="http://127.0.0.1:8012/v1"` in an uncommitted `.dev.vars`
file and run the web app on 3012. A shell variable alone is not forwarded into
the local Worker runtime. The normal frontend/API stack supplies local viewing;
no separate renderer, token transfer, or local file import is needed.

`qa/recap-browser.mjs` uses a separate headless Chrome profile under `.wrangler`
and a local debugging endpoint on 9312. It logs in, checks net/gross accounting,
exercises Previous/Play/Pause/Next, captures 1600x1000 and 390x844 screenshots,
asserts no horizontal overflow and visible controls, then verifies signed-out
private-state clearing. `RECAP_SCREENSHOT_DIR` controls the output directory.

The repository's rendered-page tests expect the offline API state. Run them
with `ALPHA_POKER_API_URL=http://127.0.0.1:9/v1` so another local API cannot alter
their expected fallback content.
