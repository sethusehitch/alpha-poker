# Alpha Poker competition E2E friction pass 5

## Verdict: FAIL

The end-to-end competition and rivalry flows completed successfully for two fresh disposable users, but the exact downloaded rivalry recap contains stale blind-escalation methodology. The public starter instructions and the actual hand logs use a 10-hand escalation interval, while `summary.json` says 20 hands. This is the sole acceptance issue in this pass.

Tested on September 7, 2026 against the visible site at `http://127.0.0.1:3013` and its documented isolated API override. No source, tests, git history, database, or prior QA reports were inspected.

## Fresh test identities

- Challenger: `p5orbit70902`, bot `Pass Five Orbit`
- Recipient: `p5ember70902`, bot `Pass Five Ember`

Passwords, cohort values, credentials, and session data are intentionally omitted.

## Timings

| Action | Observed time |
| --- | ---: |
| Fresh starter browser download | Completed at 19:47:07 PDT |
| Bundled CLI virtualenv install | 2.9 seconds |
| Two local bot validations | 0.3 seconds total in parallel |
| Slowest local bot decision | 0.11 ms and 0.12 ms |
| Unauthenticated practice failure | 0.2 seconds |
| Two 10-hand practices plus submissions | 0.9 seconds total in parallel |
| First official status check | 0.2 seconds, already complete |
| Official artifact downloads | 0.3 seconds total in parallel |
| Challenge pending window used for website verification | 35.2 seconds |
| Recipient acceptance to server completion | 0.09 seconds |
| Requests, acceptance, and bounded wait CLI sequence | 0.8 seconds |
| Two recap downloads plus post-match status checks | 0.4 seconds total in parallel |
| Verified fresh-archive journey | About 3 minutes 30 seconds |

## Actions and observed outputs

### Logged-out website

- Home page rendered the competition headline, instructions, leaderboard entry point, login control, starter download control, and copy-instructions control.
- Before any completed official run, the home page said `No official run yet.`
- The logged-out leaderboard gave an explicit empty state: `No official run has finished yet.`
- No stuck loading state appeared. Local responses resolved too quickly for the transient loading state to remain visible.
- `Copy instructions` changed visibly to `Copied` and exposed `Prompt copied to clipboard` status text.
- The versioned starter link downloaded a fresh browser artifact. The selected archive was the newly timestamped `alpha-poker-starter (16).zip`, not a previously extracted copy.
- The archive contained `README.md`, `WORKFLOWS.md`, `API.md`, `bot.py`, `bot.json`, and `cli/` as promised.

### CLI installation, bots, and practice

- Installed the bundled dependency-free CLI into a new virtual environment.
- Ran top-level and relevant subcommand help before operation.
- Built two distinct standard-library-only Python strategies and preserved the manifest API version, language, and entrypoint.
- Both bots passed four local contract checks with the verbose runner compatibility report.
- Attempting practice before account connection returned a clear HTTP 401 with `Log in first`.
- Recovered through the documented hidden registration prompts using isolated credential files and the documented API override.
- Both 10-hand practices completed and produced uniquely named ZIPs.
- Each practice ZIP contained `summary.json`, `events.jsonl`, and `hands.jsonl`.

### Official competition and Elo

- Both submissions were accepted.
- The official run completed without manual retry.
- The fresh participants' results were:
  - `Pass Five Ember`: rank 3, 1,179 Elo, 1 win and 2 losses.
  - `Pass Five Orbit`: rank 4, 1,153 Elo, 1 win and 2 losses.
- The website leaderboard matched CLI status for rank, Elo, and record.
- The official summary documented chess-style Elo settings: 1,200 starting rating, provisional K-factor 40, established K-factor 20, 10 provisional matches, and one rating update per completed best-of-five series.
- Official hand evidence for the fresh pair contained five games, ended 3-2, marked every hand as `PLHE` and `pot_limit`, and ended each game at a 20,000-to-0 stack state.
- Each participant downloaded the same official archive byte-for-byte.
- The official ZIP contained the exact promised files: `result.txt`, `summary.json`, `hands.jsonl`, and `hands.phhs`.

### Rival discovery and output formats

`rivals show` worked in all requested forms:

- Human: concise opponent, bot, Elo, and direct-record prose.
- Agent: stable facts including `username=`, `bot_name=`, `elo=`, `direct_record=`, and `is_nemesis=`.
- JSON: one valid JSON object, successfully parsed and asserted with `jq`.

Challenge status also worked in all requested forms:

- Human output reported the same 3-2 winner score from both winner and loser accounts.
- Agent output was perspective-aware: 2-3 for the challenger and 3-2 for the recipient.
- JSON was one valid object and reported `completed`, five games, 28 hands, the winner, and the 3-2 series map.

### Direct challenge website and CLI

- The challenger created a best-of-five PLHE request.
- The challenger website showed it as `PENDING`, with the recipient, timestamp, best-of-five label, and zero hands.
- The recipient CLI listed the incoming request with both current bot names before acceptance.
- Recipient acceptance moved the challenge through queued to completed.
- Final result: `Pass Five Ember` defeated `Pass Five Orbit` 3-2 across five games and 28 hands.
- The challenger website showed `LOSS`, 3-2, five-game format, and 28 hands.
- The recipient website showed `WIN`, 3-2, five-game format, and 28 hands.
- Both websites exposed a recap and focused replay links.
- The replay for game 2, hand 11 visibly labeled `SMALL BLIND` and `BIG BLIND` and stated 100 and 200 play chips respectively.
- Pre-challenge and post-challenge official ratings remained exactly 1,153 and 1,179. CLI status, website leaderboard, and recap metadata all stated that direct play did not affect Elo.

### Exact recap artifacts

- Both participants downloaded the same recap archive byte-for-byte.
- Each recap ZIP contained the exact promised files: `result.txt`, `summary.json`, `hands.jsonl`, and `hands.phhs`.
- Outcome data was internally consistent: winner, 3-2 score, five games, and 28 hands matched the CLI and website.
- `summary.json` correctly marked the challenge as direct, unofficial, unranked, play-money-only, and non-Elo-affecting.
- The sole failure is the blind-escalation methodology described below.

## Issues

### Blocker

None.

### Medium

#### Recap methodology says blinds double every 20 hands, contradicting both the public API instructions and actual evidence

Reproduction:

1. Download the current starter from the website and read the public `API.md` rivalry rules.
2. Complete a direct challenge with a game lasting more than 10 hands.
3. Download the recap with `rivals recap ... --output ... --format agent`.
4. Inspect `summary.json.methodology.blinds` and the corresponding `hands.jsonl` entries.

Observed:

- Public `API.md`: blinds double every 10 hands until a current-stack-sized sudden-death level.
- Actual game 2 logs: hands 1 through 10 use 50/100, and hand 11 uses 100/200.
- Website replay for game 2, hand 11 visibly shows small blind 100 and big blind 200.
- Downloaded recap `summary.json`: `start at 50/100 and double every 20 hands until one bot is bankrupt`.

Impact:

The downloadable evidence package is authoritative for review and reproducibility, but its methodology misstates both the escalation interval and the terminal behavior. A participant or coding agent relying on the recap can form an incorrect strategy hypothesis even though the raw hands are correct.

### Low

None.

## Acceptance summary

All requested user journeys, format variants, website perspectives, replay labels, Elo invariance checks, and artifact downloads completed. The pass is marked FAIL solely because the exact rivalry recap metadata contradicts the public rules and the actual recorded hands.
