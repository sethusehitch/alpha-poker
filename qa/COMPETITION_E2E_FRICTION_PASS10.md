# Competition E2E Friction Pass 10

## Verdict

**FAIL**

The clean two-user journey completed end to end, but the tested build did not meet the viewer-perspective contract for completed challenge status and recap in human and JSON output. Agent output was correct. This issue was reported immediately during the pass. The release owner later reported applying a fix, but that change was not rerun as part of this frozen first-time pass, so the Pass 10 verdict remains FAIL.

## Scope and constraints

- Test window: 2026-09-07 20:20:50 to 20:26:55 PDT, about 6 minutes.
- Website: `http://127.0.0.1:3018`.
- Isolated API override: `http://127.0.0.1:8018/v1`.
- Participants: `qa10_comet` with bot `Pass10 Comet`, and `qa10_harbor` with bot `Pass10 Harbor`.
- Used only the public onboarding page, its copied instructions, the freshly downloaded public starter kit, the bundled CLI, and user-visible API/CLI results.
- Did not inspect application source, tests, git state, database state, or earlier QA reports.
- No passwords, invite code, session tokens, or other credentials are included in this report.

## Timing and journey evidence

| Stage | Result | Timing or evidence |
| --- | --- | --- |
| Onboarding | PASS | Landing page clearly presented the three-step download, copy, and agent handoff flow. The copied prompt named the fresh-archive rule, required files, capability menu, safe credential flow, and approval gates. |
| Starter kit | PASS | Fresh public ZIP contained `README.md`, `WORKFLOWS.md`, `API.md`, `bot.py`, `bot.json`, `cli/README.md`, and `cli/pyproject.toml`. |
| CLI install and help | PASS | Bundled dependency-free CLI installed in a fresh virtual environment in 3.3 seconds. Top-level and relevant validate, register, train, submit, status, logs, rivals, recap, and notification help were readable. |
| Two accounts | PASS | Both users registered through hidden password, confirmation, and invite prompts, then `whoami` returned the expected username for each isolated profile. |
| Local bots | PASS | Two bots were created from the public template. Verbose validation passed in 0.07 seconds and 0.08 seconds. Each completed four contract checks with a slowest decision of 0.10 ms. |
| Practice | PASS | Each bot completed 10 hands against `house-bot`. Durations were 0.17 seconds and 0.23 seconds. Each practice ZIP contained `summary.json`, `events.jsonl`, and `hands.jsonl`. |
| First submit | PASS | `Pass10 Comet` was accepted in 0.36 seconds. Status correctly said the bot was active, the official league had not started, one more active bot was required, and Elo was not assigned. |
| Second submit and league | PASS | `Pass10 Harbor` was accepted in 0.35 seconds and the official league completed. Final Elo was 1,220 for Comet and 1,180 for Harbor. |
| Official series | PASS | Public hand evidence showed PLHE, `pot_limit`, play chips, 10,000 starting chips per player, and three completed games in the best-of-five. Comet won 3-0 over 129 hands. Game hand counts were 41, 50, and 38, each ending 20,000 to 0. |
| Official artifacts | PASS | Both users downloaded byte-identical ZIPs, SHA-256 `fb447c0ca48c944995e0f2917cf17280a78df3676d245aecd7ad3a0c95d3c3b2`. Each contained exactly `result.txt`, `summary.json`, `hands.phhs`, and `hands.jsonl`. ZIP integrity passed. Validation text was also available for each submission. |
| Challenge creation | PASS | The sender created pending challenge `ch_4976e0626613bb5e` in 0.07 seconds. CLI JSON reported best of five PLHE, score 0-0, and pending status. |
| Pending state | PASS | `rivals show` human output displayed `Current challenge: pending`; agent output included the challenge ID and `current_challenge_status=pending`. The website Challenges tab showed the outgoing request as PENDING, Best of 5, 0 hands, and the detail showed `Pending · Cancel`. |
| Accept and complete | PASS | Recipient request listing showed the correct incoming challenge. Accept returned queued in 0.06 seconds. Bounded status wait returned completed in 0.06 seconds. Result was Comet 3-0 over 123 hands and 3 games. |
| Winner and loser status | PARTIAL | Agent status was unambiguous for both viewers: `score=3-0`, `score_order=winner-loser`, and `viewer_result=win` or `loss`. Website lists were also explicit with WIN 3-0 for Comet and LOSS 3-0 for Harbor. Human and JSON CLI output failed the explicit viewer-result requirement, described below. |
| Recap artifacts | PASS | Both users downloaded byte-identical recap ZIPs, SHA-256 `ce4e1725bb0ff1e228e4e36bc6882d588e83a65b8b552ef177d033896caa2699`. Each contained exactly `result.txt`, `summary.json`, `hands.phhs`, and `hands.jsonl`; ZIP integrity passed. |
| Recap methodology | PASS | Summary identified a direct, unranked, play-money challenge; best-of-five heads-up Pot-Limit Hold'em; 10,000 starting chips per player; first to three with bankruptcy winning a game; blinds starting 50/100, doubling every 10 hands, then current-stack-sized sudden death; and no Elo effect. |
| Named blind events | PASS | Recap JSONL contained 123 `small_blind` and 123 `big_blind` named events. A keyboard-opened web replay rendered “posted the small blind” and “posted the big blind” with corresponding SMALL BLIND and BIG BLIND labels. |
| Notifications | PASS | CLI showed `You beat qa10_harbor 3-0` for the winner and `qa10_comet beat you 3-0` for the loser. JSON payloads included the winner username and per-player 3-0 series score. Website notifications showed the same winner-first 3-0 wording. |
| Keyboard accessibility | PASS | With the notification button focused, Return opened the recap. Focus landed on Close; Tab moved to the first replay link; Return opened the hand replay. The accessibility tree exposed the winner, 3-0 score, ten descriptive replay links, player names, pot, and named blind actions. |
| Elo invariant | PASS | After the direct challenge, status remained 1,220 Elo and 1-0 for Comet, and 1,180 Elo and 0-1 for Harbor. |
| Machine output cleanliness | PASS | Captured JSON status, recap, and notifications were each exactly one JSON object on a single stdout line. Stderr was empty for those completed reads. |

## Issues by severity

### High

None.

### Medium

1. **Completed challenge status does not explicitly identify the viewer result in human or JSON format.**

   - Winner and loser human status both used the same `winner qa10_comet 3-0` sentence. The only viewer-specific difference was the opponent field.
   - Status JSON contained `winner_username` and a username-keyed `series_score`, but omitted `viewer_result` and `score_order`.
   - Agent status correctly emitted winner-first `score=3-0`, `score_order=winner-loser`, and viewer-specific `viewer_result=win|loss`.
   - Impact: a person using human output does not get the requested direct win/loss statement, while a JSON consumer must infer perspective and score ordering instead of receiving the documented stable facts.

2. **Completed challenge recap does not explicitly identify the viewer result in human or JSON format.**

   - Winner and loser human recap were identical: `Pass10 Comet defeated Pass10 Harbor 3-0.` Neither said “You won” or “You lost.”
   - Recap JSON contained the winner and a username-keyed score map, but omitted `viewer_result` and `score_order`.
   - Agent recap correctly emitted winner-first `score=3-0`, `score_order=winner-loser`, and viewer-specific `viewer_result=win|loss`.
   - Impact: the same perspective ambiguity affects the post-match evidence workflow and fails the explicit winner/loser recap acceptance criterion.

### Low

None.

## Final assessment

All competition, artifact, website, notification, replay, accessibility, and Elo-invariance mechanics worked in the tested journey. The two observed defects were the missing explicit viewer perspective in completed human and JSON status, and the same omission in completed human and JSON recap. Because those behaviors were named release criteria, this pass is a decisive FAIL. A clean rerun is required to turn the reported post-pass fixes into verified acceptance evidence.
