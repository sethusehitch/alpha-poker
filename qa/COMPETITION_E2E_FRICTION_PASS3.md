# Alpha Poker Competition E2E Friction, Pass 3

**Result: FAIL**

**Test date:** 2026-09-08 UTC  
**Scope:** Black-box participant journey using only the public website, its downloaded starter kit, the surfaced CLI, and the isolated local API. No product source, repository tests, git history, prior QA reports, or pre-existing credentials were inspected. No product code was changed.

## Executive summary

The journey could not reach an official leaderboard result. Two fresh participants were created with isolated exact-path CLI profiles, two distinct bots validated locally, both completed 10-hand practice sessions, and both submissions were accepted. The official two-player round robin then remained at **0 of 1 matchups** for approximately five minutes of continuous bounded polling. The API remained healthy and responsive throughout, but no run ID, leaderboard rows, Elo, or records appeared.

Because the official result is a prerequisite for the requested website/API/CLI consistency checks and the direct-challenge Elo-invariance check, the remaining journey was not run. This pass is therefore a release-blocking FAIL rather than a partial PASS.

## Environment and cohort isolation

- Website: `http://127.0.0.1:3011`
- API: `http://127.0.0.1:8011/v1`
- Starter archive: newest browser download named `alpha-poker-starter (17).zip`
- CLI: bundled dependency-free package, reported version `0.2.0`
- Fresh participants: `p3amber191522`, `p3cobalt191522`
- Bots: `QuietComet191522`, `BriskBadger191522`
- Credentials were stored in two different exact file paths, both with mode `0600`.
- Passwords, session tokens, and cohort invite values are intentionally omitted from this report.

## Completed checks

### Website onboarding

- Landing page loaded and exposed Getting Started, Leaderboard, starter-kit download, copied-agent-instructions control, login, and account navigation.
- Starter ZIP downloaded successfully from the surfaced link.
- Login with a newly created participant succeeded.
- My Bot showed the accepted bot and the same live league progress as the CLI: `0 / 1 matchups`, with Elo, record, and rank unavailable while the run was active.

### Starter and local bot workflow

- Freshly extracted starter contained `README.md`, `WORKFLOWS.md`, `API.md`, and `cli/`.
- Relevant top-level and subcommand help was consulted before operation.
- Two simple, deliberately different Python strategies and manifests were created from the starter.
- Both bots passed all four local contract checks.
- Slowest reported local decisions were 0.12 ms and 0.11 ms.

### Account isolation

- Two new accounts registered successfully through hidden password and invite prompts.
- `whoami` returned the expected participant for each exact-path profile.
- Both credential files were mode `0600`.

### Practice

- Each bot completed a 10-hand practice session.
- Each practice produced a ZIP containing `summary.json`, `events.jsonl`, and `hands.jsonl`.
- Both summaries reported `status: completed` and `hands_played: 10`.

### Submission

- Both submissions were accepted immediately.
- CLI status for both bots consistently showed `accepted` and an active league with `0 of 1 matchups`.

## Defects and friction

### AP-P3-01: Official round robin remains at 0 of 1 and never publishes standings

**Severity: Critical, release blocker**

**Reproduction**

1. Register two fresh participants in the same isolated cohort, each using a separate exact-path CLI profile.
2. Validate and submit one active bot for each participant.
3. Run `alpha-poker status` for either participant against the cohort API.
4. Continue bounded polling.
5. Query `GET /leaderboard` during the wait and open My Bot in the website.

**Observed**

- Both submissions were accepted.
- The league repeatedly reported: `The league is playing now. Standings will refresh when it finishes.`
- Progress remained `0 of 1 matchups` for approximately five minutes, including more than four and a half minutes of repeated bounded CLI checks.
- Final observation at `2026-09-08T02:21:29Z` still showed `0 of 1 matchups` for both participants.
- At the same moment, `GET /leaderboard` returned HTTP 200 in 0.045 seconds, proving the API was responsive.
- The leaderboard payload remained empty: no run ID, update timestamp, entries, top entries, or viewer entry.
- The signed-in My Bot page agreed with the CLI and showed no Elo, record, or rank.

**Expected**

- A two-player cohort should complete its single official matchup within a practical bounded interval, advance to `1 of 1`, and publish a run ID, two leaderboard rows, Elo values, and records.
- If the match cannot finish, the run should transition to an actionable failed or timed-out state instead of remaining indefinitely active at zero progress.

**Impact**

- Participants cannot obtain an official result after successful submission.
- Website/API/CLI leaderboard consistency cannot be verified.
- Direct-challenge Elo invariance cannot be verified because there is no official pre-challenge Elo baseline.
- The complete new-participant competition journey is blocked.

### AP-P3-02: Signed-in cohort landing page shows unrelated sample standings during the live run

**Severity: Medium**

**Reproduction**

1. Log into the website as one of the fresh isolated-cohort participants.
2. Open the landing page while the cohort league is active and its API leaderboard is empty.

**Observed**

- The page displayed five polished standings for RiverRat/Maya, DeepStack/Leo, FoldEquity/Sam, RangeFinder/Noor, and ValueSeeker/Jules.
- Immediately below those standings, it also said the league was playing and standings would refresh later.
- The cohort API returned an empty leaderboard at the same time.

**Expected**

- The signed-in landing page should show the current cohort leaderboard or an explicit empty/pending state. Sample standings should be clearly labeled as examples and should not appear as live competition data.

**Impact**

- A participant can reasonably interpret demo standings as authoritative cohort results.
- The website contradicts the cohort API before the first run completes.

### AP-P3-03: Copy instructions reports success but clipboard text is unavailable

**Severity: Low**

**Reproduction**

1. Open the public landing page in Chrome.
2. Click `Copy instructions`.
3. Observe the `Copied` state and attempt to read the plain-text clipboard in the same browser session.

**Observed**

- The UI changed to `Copied` and announced `Prompt copied to clipboard`.
- The browser clipboard returned an empty string.
- The downloaded starter kit still provided enough instructions to continue.

**Expected**

- The copied prompt should be available as plain text after the success state is shown.

**Impact**

- The primary handoff from the website to a coding agent may silently fail even though the page reports success.
- Workaround: use the downloaded starter kit directly.

### AP-P3-04: My Bot briefly renders as logged out while account state loads

**Severity: Low**

**Reproduction**

1. Log in from the landing page.
2. Immediately open My Bot.

**Observed**

- The first render showed `Log in` in the account control and `Dealing you in...` in the body.
- A subsequent accessibility refresh restored the authenticated username and bot state without intervention.

**Expected**

- Preserve the authenticated shell while loading dashboard content, or show a neutral loading state without a contradictory `Log in` action.

**Impact**

- Brief but visible confusion about whether login succeeded.

## Not completed because of AP-P3-01

- Official round-robin completion.
- Leaderboard, Elo, and win/loss record agreement across website, API, and CLI.
- Direct challenge creation, acceptance, bounded completion wait, and completed-state checks from challenger and losing-recipient perspectives.
- Human, agent, and JSON output-mode parity for the completed challenge.
- Recap download and exact-file-set validation for `result.txt`, `summary.json`, `hands.phhs`, and `hands.jsonl`.
- Recap score/game/hand internal-consistency validation.
- Verification that the direct challenge caused no Elo change.

## Acceptance decision

**FAIL.** The official competition pipeline accepted both bots but did not execute or fail its only scheduled matchup within the observed interval. Re-test from two fresh cohort participants after the worker/progress defect is fixed. A passing re-test must complete the entire official and direct-challenge journey, including cross-surface records and exact recap contents.
