# Alpha Poker competition E2E friction, PASS11

Date: 2026-09-07 (America/Los_Angeles)

Environment:

- Website: `http://127.0.0.1:3019`
- API: `http://127.0.0.1:8019/v1`
- Test type: black-box, brand-new-user journey
- Product source and prior QA reports were not inspected.
- Credentials, invite values, passwords, and session tokens are intentionally omitted.

## Verdict

**FAIL**

The complete core user journey succeeded: starter discovery, local validation, registration, official competition, 400-hand practice, best-of-five PLHE challenge, bounded waiting, both-perspective output modes, notifications, Elo isolation, artifact download, website recap, and hand replay all worked end to end.

The strict PASS requirement is not met because the website accessibility check found a serious color-contrast violation, the recap dialog uses an invalid ARIA role/element combination, and the hand replay omits the actual revealed cards and evaluated hands at showdown. The latter makes a technically reachable replay substantially less useful for reviewing the decisive hand.

## Safe test identities

- Winner: `qap11alpha0907`, bot `Pass11 Pressure`
- Loser: `qap11beta0907`, bot `Pass11 Patient`
- Challenge: `ch_5b3dc68daaf3d12b`
- Rival run: `run_rival_4a455e315c412405`

These are disposable QA identities. No authentication material is included here.

## Coverage and exact evidence

### 1. First-time discovery and starter kit

1. Opened the homepage as a logged-out user.
2. Confirmed the page explains the three-step flow: download the starter kit, give it to an agent, enter the arena.
3. Confirmed the copied prompt advertises Build, Train, Compete, Challenge someone, Review hands, and Check progress, and distinguishes Elo-changing official competition from non-ranked actions.
4. Downloaded `alpha-poker-starter.zip` through the website endpoint.
5. Extracted it into a new disposable directory.
6. Verified the required files exist: `README.md`, `WORKFLOWS.md`, `API.md`, and `cli/`.
7. Read the starter documentation and CLI help before operating the product.

Result: **PASS**. The starter kit was self-contained and sufficient for a new agent-operated journey.

### 2. Build and local validation before account setup

1. Created two bots with unique names and simple, intentionally different strategies.
2. Ran local validation on each before registration.
3. Both returned:

   ```text
   Checking your bot...
   ✓ Bot check passed
   Ready to train or compete.
   ```

Result: **PASS**.

### 3. Registration and isolated profiles

1. Registered two new users through separate isolated CLI config paths.
2. Passwords and the supplied disposable invite were entered only through hidden interactive prompts.
3. Confirmed both accounts with `whoami`.

Result: **PASS**. No credential was exposed in normal CLI output or downloaded artifacts.

### 4. Submission and official competition

1. Submitted `Pass11 Pressure` first.
2. Status correctly said the bot was accepted, the official league had not started, one more active bot was required, and Elo was not assigned.
3. Submitted `Pass11 Patient` second.
4. The official league completed and produced:

   | Player | Bot | Rank | Elo | Official record | Official hands |
   | --- | --- | ---: | ---: | --- | ---: |
   | `qap11alpha0907` | Pass11 Pressure | 1 | 1,220 | 1-0 | 119 |
   | `qap11beta0907` | Pass11 Patient | 2 | 1,180 | 0-1 | 119 |

5. Downloaded the winner's validation log and official run ZIP with `logs`.

Result: **PASS**. Elo changed only after the official league completed.

### 5. Practice training is exactly 400 hands

1. Started training from the starter workflow without supplying `--hands`, exercising the documented default.
2. The training ZIP contained `summary.json`, `events.jsonl`, and `hands.jsonl`.
3. `summary.json` reported `hands_played: 400`.
4. `hands.jsonl` contained exactly 400 lines.
5. The terminal event reported `reason: hand_limit` and `hands_played: 400`.
6. Official statuses and the public leaderboard remained exactly 1,220 and 1,180 after training.

Result: **PASS**. Practice was exactly 400 hands and did not affect Elo.

### 6. Best-of-five PLHE challenge and bounded waiting

1. Used rival list/show to select the second player.
2. Sent a confirmed challenge from the first player.
3. Creation returned `format: best_of_five_plhe`, `best_of: 5`, `status: pending`, zero games, and zero hands.
4. Before acceptance, ran `rivals status ... --wait --timeout 1`.
5. It returned in approximately one second with exit code 0 and a usable check-later command.
6. The recipient saw the incoming request and accepted it.
7. A bounded 60-second wait completed successfully.
8. Final result: `qap11alpha0907` won 3-0 in 121 hands across three games.

Result: **PASS**, with one low-severity wording issue listed below.

### 7. Completed status, show, and recap in all modes from both perspectives

The following commands were exercised in `human`, `agent`, and `json` formats for both winner and loser:

- `rivals status`
- `rivals show`
- `rivals recap`

Required perspective behavior passed exactly:

- Winner human status: `completed, you won 3-0`
- Loser human status: `completed, you lost; qap11alpha0907 won 3-0`
- Winner human recap: `You won 3-0.`
- Loser human recap: `You lost; qap11alpha0907 won 3-0.`
- Winner JSON status: `viewer_result: "win"`, `winner_first_score: [3, 0]`
- Loser JSON status: `viewer_result: "loss"`, `winner_first_score: [3, 0]`
- Winner agent output: `score=3-0`, `score_order=winner-loser`, `viewer_result=win`
- Loser agent output: `score=3-0`, `score_order=winner-loser`, `viewer_result=loss`
- Winner `show` direct record: 1-0
- Loser `show` direct record: 0-1

Result: **PASS**. JSON was viewer explicit, and agent scoring stayed winner first from both viewpoints.

### 8. Notification wording and read state

Observed exact human wording:

- Received: `qap11alpha0907 challenged you. (new)`
- Winner: `You beat qap11beta0907 3-0. (new)`
- Loser: `qap11alpha0907 beat you 3-0. (new)`

The JSON notification types were `challenge_received`, `challenge_won`, and `challenge_lost`, with the expected challenge ID and snapshotted bot names. Marking each notification read succeeded. Both accounts then returned `No notifications.` and JSON `unread_count: 0`.

Result: **PASS**.

### 9. Elo changes only for official competition

1. Official competition established Elo at 1,220 and 1,180.
2. A full 400-hand practice session completed.
3. A 121-hand direct challenge completed 3-0.
4. After both non-ranked activities, CLI status and the public leaderboard were unchanged at 1,220 and 1,180.
5. Rival recap metadata independently reported:

   ```text
   official: false
   ranked: false
   affects_elo: false
   play_money_only: true
   ```

Result: **PASS**.

### 10. Exact rival recap artifacts

The downloaded challenge ZIP contained exactly these four files and no extras:

- `result.txt`
- `summary.json`
- `hands.phhs`
- `hands.jsonl`

Evidence checks:

- `result.txt` said `Pass11 Pressure defeated Pass11 Patient 3-0.`, followed by 121 hands across three games and the all-in-pot summary.
- `summary.json` used schema version 2.0, identified a `direct_rival_challenge`, marked the result non-official and non-ranked, and recorded three games totaling 121 hands.
- `hands.jsonl` contained exactly 121 records. Every record declared `game: "PLHE"` and `betting_limit: "pot_limit"`.
- `hands.phhs` contained exactly 121 hand headers and used the documented `variant = "PT"` extension.
- The per-game hand totals were 41, 42, and 38, summing to 121.
- `result.txt`, after ignoring its normal terminal newline, matched `summary.json.result_text` exactly.
- No credential, invite, bearer value, or session-token marker appeared in the checked artifacts.

Result: **PASS**.

### 11. Website UX, responsive behavior, and accessibility

The visible Mac session was locked, so the rendered UI was tested with a disposable headless Chrome browser against the same localhost website. No product source was inspected.

Covered pages and states:

- Logged-out homepage and login dialog
- Authenticated homepage
- My Bot
- Full leaderboard
- Rivals list
- Challenges tab
- Winner and loser completed-challenge cards
- Match recap drawer
- Participant-only hand replay
- Desktop at 1440 by 1000
- Mobile at 375 by 812

Positive evidence:

- Homepage language, title, headings, landmarks, links, download action, form labels, and keyboard focus order were coherent.
- Login inputs had visible associated labels.
- No horizontal overflow occurred on the tested desktop or mobile views.
- My Bot accurately showed the losing bot at 1,180 Elo, 0-1, rank 2, with official log links.
- Leaderboard marked the signed-in user's row with `YOU`.
- Winner and loser challenge cards correctly showed `WIN` or `LOSS`, a 3-0 score, best-of-five format, and 121 hands.
- Match recap explicitly said the winner, best-of-five Pot-Limit Hold'em format, and that public Elo was unchanged.
- The recap offered ten focused replay links.
- Direct replay access was participant-gated. A logged-out user was told to sign in; a participant could open it.
- Replay showed players, winner, pot, dealer, board, and a chronological narrative of blinds, returned chips, board, showdown, and result.
- Replay had no horizontal overflow and no automated accessibility violations on desktop or mobile.

Result: **FAIL overall** because of the accessibility and replay defects below.

## Issues by severity

### Medium: Homepage leaderboard column headers fail minimum color contrast

Automated WCAG checks found a serious `color-contrast` violation on the homepage leaderboard headers `Rank`, `Bot`, `Player`, `Elo`, and `Record`.

- Foreground: `#9298a2`
- Background: `#ffffff`
- Measured contrast: 2.9:1
- Required for the tested small text: 4.5:1

Impact: users with low vision may not be able to read the table labels reliably. This is the primary reason the strict overall verdict is FAIL.

### Medium: Showdown replay says cards were revealed but does not show the cards or hand ranks

For a completed showdown hand, the artifact contained both hole-card sets and evaluated categories, but the website replay only rendered `Players revealed their hand` and `SHOWDOWN`. It did not show either player's cards or the evaluated hands.

Impact: the replay is reachable and narrates the betting outcome, but it does not provide the core showdown evidence needed to understand why the winner won or to review strategy.

### Low: Match recap dialog uses an invalid ARIA role/element combination

The accessibility check reported `aria-allowed-role` on an `aside` element with `role="dialog"` and `aria-modal="true"`.

Impact: the drawer appears visually and has a labelled title, but assistive-technology behavior is not standards-compliant. Use an element/role combination that permits `dialog`, while preserving focus management and the accessible name.

### Low: Pending timeout message says `Still running`

A one-second wait on a challenge that was still `pending` returned:

```text
Still running after 1 seconds. Alpha Poker will keep working.
```

The same output also correctly showed the challenge status as pending and provided a check-later command.

Impact: a pending challenge has not been accepted and is not running. The wording could lead a first-time user to believe the poker series already started. Prefer `Still pending` or a status-specific sentence.

## Final assessment

The competition and rivalry mechanics are internally consistent and passed all requested black-box functional assertions. The two-perspective result language, winner-first agent score, explicit viewer fields, 400-hand practice boundary, non-ranked Elo isolation, notifications, and exact artifact bundle are especially strong.

Fix the homepage contrast, expose revealed showdown cards and hand categories in replay, and correct the recap dialog semantics. After those changes, rerun the website accessibility and replay portions before promoting this build to PASS.
