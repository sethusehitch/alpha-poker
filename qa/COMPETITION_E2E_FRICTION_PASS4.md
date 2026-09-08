# Alpha Poker competition E2E friction, pass 4

## Verdict: FAIL

The full two-user journey completed end to end, including account setup, local validation, practice, official competition, direct challenge, artifacts, and Elo checks. The verdict is FAIL because the losing player's human-mode CLI result reports an impossible `3-3` score, while agent mode, JSON mode, the website, and the recap all report the real `1-3` result. Two additional medium-severity presentation/state issues were also reproducible. There were no blockers.

Tested on 2026-09-07 PDT against the visible site at `http://127.0.0.1:3011`, its freshly downloaded starter kit, and the isolated test API supplied for this harness at `http://127.0.0.1:8011/v1`. Credentials were disposable and isolated. Passwords, invite values, and session tokens are intentionally omitted.

## Actions and observed results

1. Opened the logged-out home page and leaderboard.
   - Home showed `No official run yet.`
   - Leaderboard showed `No official run has finished yet.`
   - Result: PASS for empty states.

2. Clicked `Copy instructions`, navigated to the Rivals search box, and pasted.
   - Button changed to `Copied`, a `Prompt copied to clipboard` status appeared, and the complete onboarding prompt pasted successfully.
   - While the long search was processed, the website showed `Loading rivals…`, then recovered after the field was cleared.
   - Result: PASS for copy and loading states.

3. Clicked `Download starter kit`.
   - A new browser duplicate, `alpha-poker-starter (17).zip`, appeared in Downloads in under 1 second.
   - Extracted it to a new temporary folder and verified `README.md`, `WORKFLOWS.md`, `API.md`, and `cli/` before use.
   - Bundled CLI editable install and help checks completed in 3.4 seconds.
   - Result: PASS for download and onboarding.

4. Created two simple bots from the public contract.
   - `Pass4 Pressure`: smallest legal raise, then all-in/call/check/fold fallback.
   - `Pass4 Patience`: check/call/all-in/fold fallback.
   - `alpha-poker validate bot-a` and `alpha-poker validate bot-b` each returned `Bot check passed` and `Ready to train or compete` in 0.08 seconds.
   - Result: PASS.

5. Registered disposable users `pass4u193212a` and `pass4u193212b` with isolated CLI profiles.
   - Used hidden interactive password, confirmation, and invite prompts. Each registration took about 2 to 3 seconds.
   - Both `whoami` calls returned the expected username. Initial status was `Bot: no submission yet` and `League: No bot submitted yet.`
   - Logged into the website with the first CLI-created account and saw the authenticated `My Bot` and `Rivals` navigation, confirming shared account identity.
   - Result: PASS.

6. Ran 20-hand practice sessions for both bots.
   - Pressure: 0.55 seconds. Patience: 0.47 seconds. Both completed against `house-bot`.
   - Each ZIP contained exactly `summary.json`, `events.jsonl`, and `hands.jsonl`; each summary reported `status: completed` and `hands_played: 20`.
   - Result: PASS.

7. Submitted Pressure first.
   - Submission accepted in 0.35 seconds as `sub_d8ccece06ae1f53c`.
   - CLI and website both showed the truthful waiting state: active bot, waiting for one more active bot, no Elo/rank yet.
   - Result: PASS.

8. Submitted Patience second and checked both accounts immediately.
   - Submission accepted in 0.36 seconds as `sub_46d54a5990402ee6`.
   - The official round robin completed before the immediate status checks returned.
   - Website and CLI agreed: Patience rank 1 at 1,220 Elo with 1 win; Pressure rank 2 at 1,180 Elo with 1 loss.
   - Official evidence contained 120 hands across four games. Terminal game winners were Pressure, Patience, Patience, Patience, proving a best-of-five Pot-Limit Hold'em result of 3-1 for Patience.
   - Result: PASS.

9. Downloaded official artifacts for both users.
   - Each `logs` call took 0.06 to 0.08 seconds and produced exactly one validation text file plus one official ZIP.
   - Each official ZIP contained exactly the four files promised by its own manifest: `result.txt`, `summary.json`, `hands.jsonl`, and `hands.phhs`.
   - The validation logs recorded archive checks, manifest parsing, smoke validation, package acceptance, and activation.
   - Result: PASS.

10. From account A, inspected account B, sent a challenge, and checked the pending state.
    - CLI showed B at 1,220 Elo with a `0-0` direct record.
    - Challenge creation took 0.08 seconds and returned `pending`, `best_of: 5`, and `format: best_of_five_plhe`.
    - Recipient CLI and website showed the incoming challenge and unread notification. Recipient website detail showed both bots and `Accept`/`Decline` controls.
    - The challenger website's Challenges tab incorrectly showed `No direct challenges yet` while the request was pending. See issue M2.

11. Accepted from account B and waited for completion.
    - Acceptance took 0.07 seconds and returned `queued`.
    - Server timestamps show completion about 0.16 seconds after acceptance; the first bounded wait returned `completed` immediately.
    - Direct result: Patience defeated Pressure 3-1 in four games and 106 hands.
    - Winner and loser website views correctly showed `WIN`/`LOSS`, best of 5, 106 hands, 3-1, a recap, and focused hand-replay links. Both recap views explicitly said public Elo was unchanged.
    - Result: PASS for challenge execution.

12. Checked completed status from both perspectives in all output modes.
    - Winner human: winner Patience, 3-1. Winner agent: `score=3-1`. Winner JSON: series map A=1, B=3.
    - Loser agent: `score=1-3`. Loser JSON: series map A=1, B=3.
    - Loser human incorrectly printed `winner pass4u193212b 3-3`. See issue M1.
    - Both JSON outputs were exactly one stdout line and parsed as valid JSON.

13. Downloaded recap evidence from both accounts.
    - Each download took 0.07 seconds and produced one identically named ZIP.
    - Each recap ZIP contained exactly `result.txt`, `summary.json`, `hands.jsonl`, and `hands.phhs`.
    - Recap metadata stated `official: false`, `ranked: false`, `affects_elo: false`, `play_money_only: true`, and documented the best-of-five PLHE methodology.
    - Result: PASS.

14. Rechecked Elo after the direct challenge.
    - CLI status and the website leaderboard remained unchanged at Patience 1,220 and Pressure 1,180.
    - Direct history contained exactly the one completed challenge; official round-robin play was not mixed into it.
    - Result: PASS.

## Issues

### M1, medium: loser human-mode status prints an impossible 3-3 score

- Action: as losing account A, ran `alpha-poker rivals status ch_1687c69618d1f39a --format human`.
- Observed: `completed, winner pass4u193212b 3-3`.
- Expected: 1-3 from A's perspective, or 3-1 if winner-first. Agent mode, JSON, website, and recap all agree the result was 1-3/3-1.
- Impact: the default human-facing result is materially false and internally contradictory, even though machine-readable modes remain usable.

### M2, medium: challenger cannot see its pending outgoing request on the website

- Action: after account A sent the challenge, opened A's `Rivals` > `Challenges` tab and refreshed.
- Observed: `No direct challenges yet.` CLI status showed the request as pending, and account B's website showed the matching incoming request.
- Expected: the challenger should see its pending outgoing challenge.
- Impact: a normal user may resend, assume the request failed, or lose track of an open request.

### M3, medium: `rivals show --format agent` ignores the documented agent format

- Action: ran `alpha-poker rivals show pass4u193212b --format agent`.
- Observed: human prose identical to `--format human`, for example `Elo: 1,220` and `Direct challenge record: 0-0`.
- Expected: stable `key=value` facts, as promised for Rivals result commands in the public docs.
- Impact: coding agents cannot reliably parse this command without falling back to JSON.

### L1, low: hand replay labels blind events as generic placeholders

- Action: opened a focused challenge hand replay from the loser recap.
- Observed: the first two timeline rows read `Another hand event` / `HAND EVENT`; later raise, call, board, showdown, and result rows were specific.
- Expected: labels such as small blind and big blind.
- Impact: replay remains usable, but the opening action context is unnecessarily vague.

## Severity summary

- Blockers: 0
- Medium: 3
- Low: 1

