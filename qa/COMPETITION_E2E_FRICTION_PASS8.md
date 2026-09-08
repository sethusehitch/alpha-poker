# Alpha Poker Competition E2E Friction, Pass 8

## Verdict: FAIL

Clean-slate first-user acceptance completed end to end on September 7, 2026 (America/Los_Angeles) using only:

- `http://127.0.0.1:3016`
- the newly downloaded `alpha-poker-starter (16).zip`
- its bundled public documentation and CLI
- the documented process-local API override to `http://127.0.0.1:8016/v1`

No application source, tests, git state, database, or previous QA reports were inspected. Credentials and invite material are intentionally omitted.

The core competition and rivalry workflows work, but acceptance fails because two user-facing result surfaces omit the decisive score.

## Issues

### Medium: CLI human completion notifications omit the series score

The completed challenge was `pass8bravo1947` over `pass8alpha1947`, 3-2. Website notifications correctly rendered:

- Winner: `You beat pass8alpha1947 3-2`
- Loser: `pass8bravo1947 beat you 3-2`

The corresponding CLI human output rendered only:

- Winner: `You beat pass8alpha1947. (new)`
- Loser: `pass8bravo1947 beat you. (new)`

The CLI JSON notification payload was correct and contained the exact score map `{pass8alpha1947: 2, pass8bravo1947: 3}` plus `winner_username: pass8bravo1947`. This is a human-format presentation defect, not a data defect. Completion notifications are expected to include the actual winner-first score.

### Medium: Website Match recap dialog omits winner and score

The completed challenge card correctly showed `WIN` and `3 - 2`, and the notification correctly showed the winner-first `3-2`. Opening the challenge by keyboard produced a semantic dialog titled `Match recap`, but its result copy only said that the two users played a best-of-five Pot-Limit Hold'em challenge, that the first to three won, and that Elo was unchanged. It never identified the winner or stated `3-2`.

The dialog's replay links were otherwise accessible and fully operable by keyboard. The missing outcome makes the recap incomplete at its primary destination.

## End-to-end evidence

### Onboarding, install, and local validation

- Landing page clearly exposed Getting Started, Leaderboard, three onboarding steps, and a `Download starter kit` link.
- `Copy instructions` changed to `Copied` and announced `Prompt copied to clipboard`.
- Fresh browser download selected: `alpha-poker-starter (16).zip`, 28,471 bytes, downloaded at 7:47 PM local time.
- Archive contained `README.md`, `WORKFLOWS.md`, `API.md`, `cli/`, starter `bot.py`, and `bot.json`.
- Bundled CLI version installed successfully in a fresh virtual environment in 2.7 seconds.
- Top-level and relevant subcommand help were exercised before operation.
- Two isolated disposable accounts and bots were created:
  - `pass8alpha1947`, bot `Pass8 Alpha 1947`
  - `pass8bravo1947`, bot `Pass8 Bravo 1947`
- Both local validations passed all four contract checks. Slowest decisions were 0.13 ms and 0.12 ms. Combined validation command time was 0.3 seconds.

### Practice

- Both users completed 10-hand practice sessions against `house-bot`.
- Alpha practice: `trn_273bd980d3d38b75`, 0.377 seconds, 10 hands, 0 client profit chips.
- Bravo practice: `trn_64294355b98a33bd`, 0.326 seconds, 10 hands, 0 client profit chips.
- Each practice archive contained exactly `summary.json`, `events.jsonl`, and `hands.jsonl`.

### Submission and official league

- Alpha submission: `sub_61bc416fbcc9b1b1`, accepted in 0.221 seconds.
- Bravo submission: `sub_74efa50e22dcf8bb`, accepted in 0.224 seconds.
- The official run was complete on the first status check after submission.
- Official run: `run_15724ba6e97e5d23`.
- Exact official result: Bravo won the best-of-five PLHE series 3-1 across 208 hands.
- Game evidence:
  - Game 1: Alpha, 53 hands
  - Game 2: Bravo, 62 hands
  - Game 3: Bravo, 51 hands
  - Game 4: Bravo, 42 hands
- Elo and records:
  - Bravo: rank 1, 1,220 Elo, 1-0
  - Alpha: rank 2, 1,180 Elo, 0-1
- Validation logs confirmed archive safety, manifest parsing, `bot.py` presence, isolated smoke validation, acceptance, and activation.
- Exact official archive files:
  - `result.txt`
  - `summary.json`
  - `hands.jsonl`
  - `hands.phhs`
- Official `summary.json` declared Elo ranking, 1,200 starting rating, provisional K=40, established K=20, ten provisional matches, and one rating update per completed best-of-five heads-up PLHE tournament series.

### Direct challenge

- Challenge: `ch_c0c8de1c8441a6e3`.
- Challenge creation correctly returned `pending`, `best_of: 5`, `format: best_of_five_plhe`, and score 0-0.
- The sender could immediately inspect the outgoing pending challenge in human, agent, and JSON status output.
- The recipient's incoming list exposed the same pending request in human, agent, and JSON formats.
- Pending duration before acceptance: 12.79 seconds.
- Acceptance returned `queued`; accepted-to-completed engine time was about 228 ms.
- Direct run: `run_rival_1b15974ee4c6e08b`.
- Final result: Bravo beat Alpha 3-2 across 5 games and 256 hands.
- Game winners and hands:
  - Game 1: Bravo, 53 hands
  - Game 2: Bravo, 45 hands
  - Game 3: Alpha, 53 hands
  - Game 4: Alpha, 47 hands
  - Game 5: Bravo, 58 hands

Winner and loser result surfaces were otherwise consistent:

- Human status and recap used the winner-first result `Pass8 Bravo 1947 defeated Pass8 Alpha 1947 3-2`.
- Agent format was intentionally viewer-relative: winner saw `score=3-2`; loser saw `score=2-3`.
- JSON named `winner_username: pass8bravo1947` and mapped Alpha to 2, Bravo to 3.
- `rivals show` correctly reported the winner's direct record as 1-0 and the loser's as 0-1 in human, agent, and JSON formats.
- The winner and loser could each download the same recap evidence archive.

### Recap evidence and methodology

- Exact recap archive files:
  - `result.txt`
  - `summary.json`
  - `hands.jsonl`
  - `hands.phhs`
- Recap `summary.json` correctly declared:
  - `official: false`
  - `ranked: false`
  - `affects_elo: false`
  - `play_money_only: true`
  - 10,000 starting chips per bot per game
  - first to three game wins, with bankruptcy ending a game
  - blinds starting at 50/100, doubling every 10 hands, then current-stack-sized sudden death
- The hand artifact contained 256 `small_blind` and 256 `big_blind` named events.
- Observed levels advanced at hands 1, 11, 21, 31, 41, and where needed 51: 50/100, 100/200, 200/400, 400/800, 800/1600, and 1600/3200.

### Website accessibility and keyboard path

- Logged-in navigation exposed semantic links for My Bot and Rivals, plus a notification button with an unread count.
- Challenges used a selectable tab and a semantic `Open` button.
- From the selected Challenges tab, one Tab keystroke focused `Open`; Enter opened the dialog.
- Focus moved to the dialog's `Close` button.
- The dialog had the accessible name `Match recap` and ten named replay links such as `Hand 52 won by pass8bravo1947 Open replay`.
- Tab focused the first replay link; Enter navigated to the replay page.
- The replay page exposed player names, winner, 17,600-chip pot, dealer, board, and named events including:
  - `pass8bravo1947 posted the small blind of 1,600 play chips`, labeled `SMALL BLIND`
  - `pass8alpha1947 posted the big blind of 3,200 play chips`, labeled `BIG BLIND`
- Winner and loser website notifications both used the actual winner-first score `3-2` and opened the associated recap.

### Elo isolation

- Before the direct challenge: Bravo 1,220; Alpha 1,180.
- After the direct challenge: Bravo 1,220; Alpha 1,180.
- Direct play did not change public Elo, as required.

## Severity summary

- Critical: 0
- High: 0
- Medium: 2
- Low: 0

All competition mechanics, evidence generation, score data, Elo isolation, replay navigation, and named blind-event rendering passed. The release candidate fails Pass 8 because the CLI human notification and the primary website Match recap omit decisive result information.
