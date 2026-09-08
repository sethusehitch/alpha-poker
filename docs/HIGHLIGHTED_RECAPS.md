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

Completed recaps show both players' retained hole cards throughout, including
folded hands. Direct challenge access remains limited to participants.
Game and hand numbers distinguish tournament hands, and ordering is chronological
by game then hand. Cross-game cumulative chip lead labels are disabled because
stacks reset between tournament games. Detailed bot-error strings are not
included. Poker categories are evaluated from actual revealed cards and board;
folds and bot forfeits have explicit descriptions. Missing values remain
unavailable rather than being presented as zero. Responses are `private,
no-store`, and the browser discards cached recap state when the account changes.

The current highlight title appears on an animated banner with game/hand context.
One sidebar control area below the player cards contains previous/next
highlight arrows, Replay (restart the whole hand at step 1), and Play/Pause.
Every hand initially opens at its final result. There is no bottom control bar,
timeline, or duplicated action history. Compact step progress and the current
action remain inside the table. The pot at a result is labeled **Pot awarded**,
while player stacks show their post-award balances.

At the final result only, the recorded winning seat receives a restrained gold
accent and explicit Winner badge. A loss highlights the opponent; a split pot
marks both seats as Split pot. Unknown winners receive no gold accent. Cobalt
continues to indicate the recorded actor during playback.

Optional `recap-v1` step fields `actor_seat`, `action_kind`, `committed_amount`,
`pot_before`, and `action_label` make each recorded action explicit. Seats remain
physical engine seats, with usernames mapped before rendering. Payments use
the event's `amount`, never its raise-to target. Checks/folds commit zero; missing
payments stay null. Unknown metadata in older payloads renders without a flight.
Board, reveal, forfeit, and result steps have a neutral table state.

The acting badge gets a cobalt ring. A recorded positive payment flies from that
badge to its **seat wager**, not to the central pot, over 1040ms. Seat wagers
accumulate through the current street. Optional `table_chips` metadata is
versioned `street-wagers-v1`; it includes before/after wagers, gathered pot, and
explicit sweep amounts. The old `step.pot` remains the total for older clients.
The center shows **Gathered pot**, excluding every outstanding wager.

At a retained street boundary, a neutral gather step lifts both wager stacks
and sweeps them to the center together. Source stacks disappear while in flight;
the center updates and wagers clear when both flights arrive. This happens before
new board cards or final award/gold state. Empty streets add no empty sweep.
Preflop folds and all-in runouts gather exactly once. A missing payment stays
unknown, never inferred from a raise target or total; a recorded authoritative
total can restore the gathered pot only once all wagers have been cleared.
Missing-start legacy fragments do not invent initial contributions. Old payloads
without a ledger show **Total pot** and no invented wager animation.

Each visited step owns a keyed presentation, so Replay and highlight navigation
cannot accumulate chips or retain a stale flight. Pausing leaves current chips
to settle without advancing the action. Replay also resets the action timer if
pressed again on step 1. Reduced motion shows the correct destination immediately.
Action cadence remains 2200ms; both payment and sweep animations remain 1040ms.

## Win chance / retrospective showdown equity

Optional `equity` metadata is versioned `showdown-equity-v1`. Calculation runs
server-side using the same `alpha_poker.evaluator.evaluate` as the engine. It
requires a completed showdown result and **two explicit, valid hole-card reveals**.
Folded/mucked cards, one-sided reveals, malformed cards, forfeits, and missing
board evidence produce no equity. Even a viewer's own retained cards do not
bypass this gate. The authorization and per-step card-visibility rules are
unchanged. Eligible odds are retrospective, conditioned on both legitimately
revealed hands, even while the animation has not yet exposed those cards.

Only the current board and the four known hole cards are removed from the deck.
Future runout cards are not used early. Flop, turn, and river enumerate all
990, 44, and 1 remaining runouts exactly. Ties count as half a win for each seat,
so "Win chance" is pot-share equity, not outright win probability. One percentage
is rounded to a tenth and the other is its complement.

Preflop has 1,712,304 possible boards. A timed exact 10,000-board prefix took
0.95s locally, projecting about 163 seconds for full enumeration. Instead, we
sample **2,048 distinct uniformly sampled boards**, with fixed seed 20260907.
Preflop is visibly marked **estimated**. Its nominal worst-case binomial 95%
sampling error is about **±2.2 percentage points**, not a guaranteed bound on
this fixed sample. The accessible tooltip and payload include this margin.
Suit/rank order is canonicalized and seats are mapped back, so mirrored seats
receive complementary results without a second calculation.

A per-recap cache and bounded 128-entry evaluator LRU reuse identical states.
Selection-only normalization never computes equity. The local benchmark measured
0.198s for cold preflop, 0.093s flop, 0.004s turn, and <0.001s river. Five distinct
cold hands across all streets took **1.507s**, below the <=2.5s local target.
The test guard allows 3.5s for scheduling headroom; cache reuse is tested separately.
Run `qa/recap_equity_benchmark.py` to reproduce the bounded benchmark.

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
checks sidebar-only controls and heading/context, exercises Replay/Play/Pause
and highlight arrows, checks both physical actors, accumulated seat wagers,
simultaneous street sweeps and central-pot accounting, changing equity when the
board arrives, interrupted flights, and reduced motion. It plays the entire
hand at its real 2200ms cadence and verifies final-only gold. Action, sweep, and
final screenshots are captured at 1600x1000 and 390x844. It asserts no horizontal
overflow and visible controls, then verifies signed-out private-state clearing.
`RECAP_SCREENSHOT_DIR` controls the output.

The repository's rendered-page tests expect the offline API state. Run them
with `ALPHA_POKER_API_URL=http://127.0.0.1:9/v1` so another local API cannot alter
their expected fallback content.
