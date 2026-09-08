# Alpha Poker Competition E2E Friction Pass 6

## Verdict

**FAIL due to one P2 accessibility issue.** All requested functional flows completed, but the web recap was not accessible through the semantic UI tree during this pass.

The complete clean-slate two-account journey succeeded against only:

- Web: `http://127.0.0.1:3014`
- API override: `http://127.0.0.1:8014/v1`
- Public website instructions and the newly downloaded starter kit

No application source, test files, Git state, database, or prior QA reports were inspected.

## Test identities and outputs

- Player A: `pass6atlas907`, bot `Pass6 Comet`
- Player B: `pass6birch907`, bot `Pass6 Willow`
- Official run: `run_979f9c39c7f6688f`
- Direct challenge: `ch_b23ca8276e197360`
- Rival run: `run_rival_4d12ea9050205cb5`

Passwords, invite values, session tokens, and credential contents are intentionally omitted.

## Acceptance results

### Onboarding and public UI

- **PASS - Initial empty state.** The fresh homepage rendered `No official run yet.` before either account submitted.
- **PASS - Loading and route transitions.** The first local page became usable in about 0.69 seconds. Subsequent authenticated routes settled in about 0.24 to 0.42 seconds without a stale or blank terminal state. The loading treatment was too brief to remain visually observable on this local server, but the settled states were correct.
- **PASS - Copy instructions.** `Copy instructions` changed to `Copied` and exposed `Prompt copied to clipboard` in the accessibility tree in about 0.34 seconds.
- **PASS - Download.** The website download produced the newest browser duplicate, `/Users/sethsaperstein/Downloads/alpha-poker-starter (16).zip`, 28,471 bytes. The kit contained `README.md`, `WORKFLOWS.md`, `API.md`, `bot.py`, `bot.json`, and the bundled `cli/` package.
- **PASS - Authenticated waiting state.** After the first submission, My Bot displayed `Pass6 Comet`, `In the league`, and `Waiting for 1 more active bot before the next league run.` with Elo, record, and rank shown as unassigned.
- **PASS - Public leaderboard.** After the second submission, the web leaderboard showed `Pass6 Comet` at 1,220 Elo and 1-0, and `Pass6 Willow` at 1,180 Elo and 0-1.

### CLI installation, bot creation, and local validation

- **PASS - Documented override.** All hosted CLI operations used `ALPHA_POKER_API_URL=http://127.0.0.1:8014/v1` for the current process.
- **PASS - Isolated profiles.** Each player used a separate exact `ALPHA_POKER_CONFIG` file.
- **PASS - Install.** A fresh virtual environment installed the bundled dependency-free CLI as `alpha-poker-cli 0.2.0` in about 2.8 seconds.
- **PASS - Help-first operation.** Top-level help and the relevant `validate`, `train`, `submit`, `logs`, `rivals show`, `rivals challenge`, `rivals requests`, `rivals accept`, `rivals status`, and `rivals recap` help were reviewed before use.
- **PASS - Two distinct bots.** The first deterministic bot preferred maximum legal aggression. The second checked when possible and folded to bets. Both preserved the documented manifest version, language, and entrypoint.
- **PASS - Local validation.** `Pass6 Comet` passed in 0.08 seconds. `Pass6 Willow` initially returned the precise actionable error `NameError: name 'legal' is not defined`; after adding the omitted local variable, the normal retry passed in 0.08 seconds. This exercised the documented user-facing repair loop without touching server state.

### Registration, practice, submission, and official competition

- **PASS - Registration.** Both new accounts registered through hidden interactive password and cohort-code prompts. Each registration completed in roughly 3.4 seconds and immediately reported the correct logged-in username.
- **PASS - Practice.** Player A completed a 10-hand local-bot practice session against the hosted leader in 0.17 seconds. The explicit output path created `practice-a.zip` with exactly `summary.json`, `events.jsonl`, and `hands.jsonl`. The summary reported `completed`, 10 hands, and `house-bot` as the frozen leader.
- **PASS - Two submissions.** `Pass6 Comet` was accepted as `sub_e4e12f0979c3f317` in 0.36 seconds. `Pass6 Willow` was accepted as `sub_edf9b3cba7c72dcb` in 0.36 seconds.
- **PASS - Official best-of-five PLHE.** The official run completed immediately after the second active bot arrived. Its summary identifies heads-up pot-limit hold'em tournament games and Elo rating once per completed best-of-five series. Hand evidence grouped into three games, all won by Player A, so the series correctly stopped at 3-0. Game hand counts were 38, 38, and 41, totaling 117.
- **PASS - Elo.** The starting 1,200 ratings moved by the documented provisional K-factor outcome to 1,220 for Player A and 1,180 for Player B.

### Exact official artifacts

Both players downloaded their validation file and the same official evidence ZIP in about 0.06 seconds each.

- Player A validation: `sub_e4e12f0979c3f317-validation.txt`
- Player B validation: `sub_edf9b3cba7c72dcb-validation.txt`
- Official ZIP: `run_979f9c39c7f6688f-official-logs.zip`
- ZIP size: 10,155 bytes
- SHA-256 from both accounts: `ea5501a73463d99d7b52da4b01c8a95e17bc1ca0a9ed8fb79a0ebf8b980f4ff6`
- Exact ZIP members: `result.txt`, `summary.json`, `hands.jsonl`, `hands.phhs`

The two independently downloaded official ZIPs were byte-identical. Both validation logs ended with `Isolated smoke validation complete. Package accepted.` and `Submission activated.`

### Direct challenge

- **PASS - Rival discovery and `rivals show`.** Before the challenge, human, agent, and JSON views agreed on Player B's bot, 1,180 Elo, and a 0-0 direct record.
- **PASS - Send.** Player A sent a best-of-five PLHE request in 0.07 seconds. JSON reported `pending`, `best_of: 5`, and `format: best_of_five_plhe`.
- **PASS - Outgoing sender visibility.** Player A's web Challenges tab immediately showed the pending outgoing challenge to `pass6birch907`, `Best of 5`, zero hands, and an enabled Open control. Opening it showed the opponent, 0-0 score, and `Pending - Cancel` state.
- **PASS - Recipient views and accept.** Player B's incoming human, agent, and JSON views all identified the same pending challenge. Acceptance took 0.07 seconds and returned `queued` with both snapshotted bot names.
- **PASS - Completion.** The server ran from `02:55:54.687405Z` to `02:55:54.765430Z`, about 78 ms. Final result was Player A over Player B, 3-0 across 124 hands.
- **PASS - Winner and loser human, agent, and JSON outputs.** From Player A, status showed opponent `pass6birch907`, score `3-0`, and winner `pass6atlas907`. From Player B, status showed opponent `pass6atlas907`, viewer-relative score `0-3`, and the same winner. Human prose, stable agent facts, and JSON agreed.
- **PASS - Post-match `rivals show`.** Player A saw a 1-0 direct record against Player B. Player B saw 0-1 against Player A. Human, agent, and JSON outputs agreed, and both JSON histories contained the completed challenge.
- **PASS - Recap outputs.** Human, agent, and JSON recap views from both players agreed on winner, 3-0 score, 3 games, and 124 hands. Agent score remained viewer-relative, while JSON retained the canonical named series score.

### Exact recap artifacts and blind schedule

`rivals recap --output` created `alpha-poker-rival-ch_b23ca8276e197360.zip` in about 0.07 seconds.

- ZIP size: 11,837 bytes
- SHA-256: `7a460986df6e5304854f81a809c5ae38868f59e32092cfdd2a02d62cbb1d5c07`
- Exact ZIP members: `result.txt`, `summary.json`, `hands.jsonl`, `hands.phhs`
- `summary.json` explicitly reported `official: false`, `ranked: false`, `affects_elo: false`, and `play_money_only: true`.

The recap methodology matched the actual hand evidence:

- Declared: start at 50/100, double every 10 hands, then use current-stack-sized sudden death until bankruptcy.
- Observed in every completed game: hands 1-10 at 50/100, hands 11-20 at 100/200, hands 21-30 at 200/400, and hands 31-40 at 400/800.
- Observed in game 2, which reached 46 hands: hands 41-46 at 800/1600.
- Games 1 and 3 ended on hand 39, and game 2 ended on hand 46, so no later sudden-death level was needed.
- Each game started 10,000 to 10,000 and ended 20,000 to 0 for Player A, matching the bankruptcy win condition.

### Replay labels and Elo isolation

- **PASS - Replay labels.** Focused replay for game 1 hand 31 rendered `SMALL BLIND` with 400 and `BIG BLIND` with 800. Focused replay for game 2 hand 41 rendered `SMALL BLIND` with 800 and `BIG BLIND` with 1,600. The event text, labels, and downloaded hand JSON agreed.
- **PASS - Elo unchanged by challenge.** Immediately after the challenge, both CLI status and the web leaderboard still showed 1,220 and 1,180 with the original 1-0 and 0-1 official records. No new official run or rating change occurred.

### Normal recovery paths

- **PASS - Bot repair.** The local validator gave an actionable source error and a normal retry succeeded after the one-line fix.
- **PASS - Web login recovery.** After logging out, an intentionally incorrect password kept the form open and displayed `Username or password is incorrect`. Replacing it with the correct credential logged in successfully without losing leaderboard state.
- **PASS - URL/state continuity.** Challenge links preserved rival and result context when moving from the recap to focused hand replay and back to Rivals.

## Issues by severity

### P2 - Match recap overlay is absent from the accessibility tree

**Observed:** Clicking `View recap` visibly opened the Match recap overlay with the methodology sentence and multiple `Open replay` controls. However, repeated full accessibility-tree captures exposed only the underlying rival drawer. The overlay heading, completion copy, focused-hand rows, Close control, and Open replay controls were missing.

**Impact:** Screen-reader users and semantic keyboard/automation clients cannot discover or operate the visible recap. Functional mouse users can continue, and a coordinate click successfully opened the hand replay, but the missing semantic access fails this acceptance pass.

**Suggested fix:** Give the overlay a properly exposed dialog role and accessible name, avoid applying hidden/inert state to the dialog subtree, move focus into it when opened, expose each replay control as a named button or link, and restore focus on close.

No P0 or P1 issues were found. No server error, stuck run, artifact mismatch, score disagreement, blind-schedule mismatch, or Elo leak was observed.
