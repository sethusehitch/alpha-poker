# Alpha Poker Competition E2E Friction, Pass 1

## Result

**FAIL**

The first-time participant journey succeeds through onboarding, starter-kit setup, local validation, account creation, short practice, two bot submissions, rival discovery, and sending a challenge. It does not complete the official competition or direct-challenge journeys. The isolated API stayed at `0 of 1 matchups` for about ten minutes, challenge acceptance timed out twice while the request remained pending, and the API then stopped accepting connections entirely.

Because of that failure, this pass could not verify completed official standings/Elo/records, a best-of-five result, recap modes, or the downloaded evidence ZIP and its required four artifacts.

## Scope and method

- Website tested as a participant through the visible UI at `http://127.0.0.1:3014`.
- Bundled starter kit downloaded from the website and inspected as participant-facing material.
- Bundled CLI installed into a fresh virtual environment under an isolated temporary directory.
- Two disposable accounts used separate exact-path CLI profiles. Stored profile permissions were `0600`.
- Two distinct bots were created: `Pass One Hawk` (tight/aggressive) and `Pass One Turtle` (calling-oriented).
- Hosted actions were limited to the isolated local test API at `http://127.0.0.1:8011/v1`.
- No production service was contacted. No product code, repository source, tests, or git history were inspected or changed.
- No password, session token, invite value, or credential is included in this report.

## Successful acceptance evidence

### Landing and starter kit

- Landing page clearly presents the sequence: download starter kit, give it to a coding agent, then enter the arena.
- Public homepage and dedicated leaderboard page are readable and provide rank, bot, player, Elo, and record labels.
- Download stays on the landing page and produces a ZIP successfully.
- The most recently downloaded archive was selected instead of silently reusing an older browser duplicate.
- ZIP contained the expected participant material: `README.md`, `WORKFLOWS.md`, `API.md`, `bot.py`, `bot.json`, and bundled `cli/` package files.
- Starter documentation clearly explains bot constraints, local validation, practice, submission, league minimums, rival discovery, notifications, and artifact downloads.

### CLI setup, accounts, and validation

- Bundled CLI version `0.2.0` installed successfully in a clean virtual environment.
- Top-level and relevant subcommand help rendered without installation/runtime errors.
- An unauthenticated `status` exits nonzero and says: `not logged in; run alpha-poker login USERNAME`.
- Registration uses hidden password, confirmation, and invite prompts rather than requiring secrets in normal command arguments.
- Both isolated profiles were stored with `-rw-------` permissions.
- `whoami` correctly identified each disposable account.
- Local validation succeeded for both bots:
  - `Pass One Hawk`: 3 contract checks, maximum reported decision time 0.01 ms.
  - `Pass One Turtle`: 3 contract checks, maximum reported decision time 0.00 ms.

### Practice

- Invalid `--hands 0` fails safely with the useful range error: `--hands must be between 1 and 10000`.
- A 10-hand practice completed quickly against `house-bot`.
- Passing a directory to `--output` created a uniquely named ZIP inside that directory, as documented.
- Practice ZIP contained `summary.json`, `events.jsonl`, and `hands.jsonl`.
- `summary.json` was concise and understandable, including training ID, participant, leader, status, hands played, timestamp, and client chip profit.

### Submission and pre-failure league status

- Both submissions returned accepted submission IDs.
- Status for both accounts correctly showed the active bot as accepted.
- Status initially explained that the league was playing and that standings would refresh when it finished.
- Matchup progress was displayed as `0 of 1 matchups`.

### Rival discovery and request delivery

- Human rival listing showed the opponent bot, Elo, and direct record.
- JSON rival search emitted a stable object containing bot name, Elo, active-bot state, direct record, rank, and username.
- Human rival detail displayed bot, Elo, and direct record.
- Sending the pre-approved challenge succeeded and returned a pending challenge with both bot names.
- The recipient could see the request in both human and JSON request listings.
- JSON challenge state exposed useful series fields: `best_of: 5`, format, games completed, current game, series score, winner, and timestamps.

## Friction and defects

### [Critical] Official league never advances and the isolated API eventually stops listening

**Reproduction**

1. Register two isolated disposable accounts.
2. Validate and submit one active bot for each account.
3. Run `alpha-poker status` repeatedly against the isolated API.
4. Observe `League: The league is playing now` and `Progress: 0 of 1 matchups` for about ten minutes with no progress.
5. Continue checking until both CLI and direct public leaderboard requests fail with connection refused.

**Observed**

- No official matchup completed.
- The public API leaderboard remained empty before the crash (`run_id: null`, no entries).
- The service then stopped listening on port 8011.
- The CLI reported it could not reach the account status endpoint.

**Expected**

- The one required matchup should start and complete within the advertised server-side deadline.
- Status should move through useful progress and finish with a durable result.
- A failed run should remain visible as an actionable failed state without taking down the API.

**Impact**

Blocks the core competition promise and all downstream verification: official result, leaderboard refresh, Elo, record, official logs, and reliable challenge queue processing.

**Unblock criteria**

- Restart the isolated service with durable state if intended, repair the worker/queue failure, and demonstrate that a fresh two-bot cohort completes one official matchup while the API stays healthy.

### [High] Challenge acceptance times out twice and leaves the request pending

**Reproduction**

1. From Account A, send a challenge to Account B with `rivals challenge ... --yes --json`.
2. Confirm Account B sees the incoming request.
3. From Account B, accept with `rivals accept CHALLENGE_ID --yes --json`.
4. Wait for the CLI's 30-second request timeout.
5. Check challenge state from Account A, then retry the documented acceptance action once.

**Observed**

- Both accept attempts ended with: `Alpha Poker did not respond within 30 seconds. Try again; your local bot files are unchanged.`
- After the first timeout and during the second attempt, challenge state remained `pending`, with no acceptance/start timestamps.
- Acceptance did not return stable JSON on stdout because the request never completed.

**Expected**

- Acceptance should return promptly with an idempotent accepted/queued state.
- Match execution should be asynchronous, with bounded `rivals status --wait` handling the wait.
- A retry after a network timeout should safely return the same accepted challenge or a clear terminal error.

**Impact**

Blocks recipient acceptance, bounded waiting, completed best-of-five result, recap, notifications, and evidence download.

### [High] Website and isolated API present incompatible account and league state

**Reproduction**

1. Create a disposable account successfully with the CLI against the isolated API.
2. Use the website's `Log in` dialog with the same account.
3. Refresh the homepage and open the dedicated leaderboard page while the isolated API reports a two-bot league running.

**Observed**

- Website login says `Username or password is incorrect` for the valid isolated API account.
- Website displays an unrelated seeded five-player leaderboard.
- Website says `Waiting for 1 more active bot before the next league run` while the isolated API says a two-bot league is playing.

**Expected**

- In an end-to-end local test environment, the website and documented test API should share account, leaderboard, and league readiness state, or the test instructions should explicitly state that they are intentionally separate fixtures.

**Impact**

A participant cannot use the website to confirm the account, active bot, competition state, or result created through the supplied CLI.

### [Medium] Starter documentation describes the wrong direct-challenge format

**Reproduction**

1. Read `README.md`, `WORKFLOWS.md`, `API.md`, and `cli/README.md` from the downloaded kit.
2. Send a challenge and inspect the returned JSON.

**Observed**

- Documentation repeatedly promises one `200-hand mirrored` heads-up match.
- CLI confirmation also says `one 200-hand direct challenge`.
- Live JSON instead reports `format: best_of_five_plhe` and `best_of: 5`, with game-level progress and series score.

**Expected**

- Website, starter documentation, CLI confirmation, help, API response, recap, and evidence should use one consistent best-of-five description, including how many hands or games determine each result.

**Impact**

The participant is asked to approve a materially different competition format from the one the server actually records.

### [Medium] Practice range and default are not discoverable from `train --help`

**Reproduction**

1. Run `alpha-poker train --help`.
2. Look for the allowed values and default for `--hands`.
3. Run with `--hands 0` to force validation.

**Observed**

- Help lists `--hands HANDS` without a range or default.
- The range `1 to 10000` becomes visible only after an invalid attempt.
- The default remains undisclosed in help.

**Expected**

- Help should say something equivalent to `number of practice hands (1-10000, default: N)`.

**Impact**

Agents and participants cannot choose a short or representative practice run confidently without trial and error.

### [Medium] No distinct agent-readable status or recap mode is exposed

**Reproduction**

1. Run `rivals status --help` and `rivals recap --help`.
2. Attempt `--agent` on both commands.

**Observed**

- Only default human output and `--json` are exposed.
- `--agent` is rejected as an unrecognized argument with exit code 2.
- Completed human/JSON recap output could not be reached because challenge acceptance and the API failed.

**Expected**

- If human, agent, and JSON are required product surfaces, help should name all three and the CLI should render each consistently.
- If JSON is the intended agent mode, product requirements and participant docs should call that out explicitly instead of referring to a third mode.

**Impact**

The requested three-format acceptance check is impossible from the shipped CLI surface.

### [Low] Human incoming-request output omits decision context

**Reproduction**

1. Receive a pending challenge.
2. Run `rivals requests --status incoming` without `--json`.

**Observed**

- The line contains challenge ID, challenger username, and `pending` only.
- It omits both current bot names and the best-of-five format.

**Expected**

- Human output should include both bot names and the format so the recipient can make the approval decision without a second command.

**Impact**

Small but avoidable friction at a confirmation-protected action.

## Required evidence ZIP verification

**Blocked by upstream failures.** No completed challenge recap or evidence archive became available.

The pass therefore did **not** verify that a downloaded archive contains exactly these four artifacts:

1. `result.txt`
2. `summary.json`
3. `hands.phhs`
4. `hands.jsonl`

It also could not verify that those four contents agree and are understandable. This remains a mandatory rerun item after the critical league/API and challenge-acceptance failures are fixed.

## Rerun checklist

1. Start with a fresh disposable cohort and two fresh isolated profiles.
2. Confirm website and API point at the same environment before registration.
3. Submit two distinct bots and require the official league to reach a completed result.
4. Verify both accounts' Elo and win/loss/draw records in CLI, public API, and website.
5. Send and accept a best-of-five challenge, then use a bounded `--wait` call.
6. Capture completed status and recap in every supported human/agent/JSON mode.
7. Download the evidence ZIP, assert exactly four top-level files, open each, and cross-check winner, score/margin, games, hands, and identifiers.
