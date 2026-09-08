# Alpha Poker competition E2E friction pass 7

## Verdict: FAIL

The clean-slate onboarding, official league, direct rival challenge, artifact, multi-format, accessibility, keyboard, replay, and Elo invariance assertions completed successfully against the isolated site and API. The run fails acceptance because the losing participant's completion notification reported a nonexistent zero-chip margin instead of the actual 3-1 series score. No source, git history, repository tests, database, or prior QA report was inspected.

Tested on September 7, 2026 Pacific time (September 8 UTC).

## Scope and test identities

- Website: `http://127.0.0.1:3015`
- Isolated API override: `http://127.0.0.1:8015/v1`
- Selected download: `/Users/sethsaperstein/Downloads/alpha-poker-starter (16).zip`
- Fresh extraction: `/tmp/alpha-poker-pass7.7iO483`
- Accounts: `pass7ace0907`, `pass7river0907`
- Bots: `Pass7 Ace`, `Pass7 River`
- Credentials and invite material are intentionally omitted.

## Timing and outcome

| Stage | Evidence and timing | Result |
| --- | --- | --- |
| Site copy and kit download | Copy button changed to `Copied` with `Prompt copied to clipboard`. The newest matching archive was selected and contained `README.md`, `WORKFLOWS.md`, `API.md`, and `cli/`. | PASS |
| CLI install and help | Editable install of bundled dependency-free CLI completed in 3.1 seconds. Top-level plus validate, train, submit, status, logs, and rivals help were exercised. | PASS |
| Local build and validation | Both distinct bots passed four contract checks before practice. Slowest decisions were 0.12 ms and 0.11 ms. | PASS |
| Account connection | Both disposable accounts registered through hidden password and invite prompts using isolated credential files and the documented API override. `whoami` returned the expected username for each. | PASS |
| Practice | From `03:01:17Z` to `03:01:19Z`, both bots completed 40 hands against `house-bot`. Pass7 Ace finished +11,340 chips; Pass7 River finished -80 chips. Each ZIP contained `summary.json`, `events.jsonl`, and `hands.jsonl`. | PASS |
| Practice review and iteration | Hand logs were inspected. Pass7 Ace was strengthened to recognize made pairs with the board. Pass7 River was widened to continue with suited or connected holdings. Both passed validation again, at 0.11 ms and 0.10 ms slowest decision. | PASS |
| First submission and wait state | At `03:01:40Z`, Pass7 Ace submission `sub_25e890f7a75012a2` was accepted. Status correctly said the official league had not started and was waiting for one more active bot, with no Elo assigned. | PASS |
| Second submission and official league | Pass7 River submission `sub_2d7b34e0dcbaf4f8` was accepted. By `03:01:41Z`, official run `run_eeac5ef66e0f6085` was complete. Hand evidence reports `game=PLHE`, `betting_limit=pot_limit`, 50/100 opening blinds, and three tournament games. | PASS |
| Official result and Elo | Pass7 Ace ranked 1st at 1,220 Elo with a 1-0 series record. Pass7 River ranked 2nd at 1,180 Elo with a 0-1 series record. The leaderboard reported 125 hands per participant. | PASS |
| Pending challenge | At `03:02:07Z`, challenge `ch_866c565c7ed7038b` was created as `best_of_five_plhe`. Sender JSON reported `pending`. The sender's website Challenges tab visibly showed `PENDING`, the recipient's tab showed the incoming request, and recipient human/agent/JSON request views agreed. | PASS |
| Accept and complete | Accepted at `03:02:41.062835Z`; completed at `03:02:41.221807Z`; observed complete by `03:02:44Z`. Pass7 Ace won 3-1 over four games and 135 hands. | PASS |
| Both perspectives and output formats | Human, agent, and JSON were exercised from both accounts for completed status, `rivals show`, history, and recap. Scores were correctly perspective-aware in agent output (3-1 for the winner, 1-3 for the loser), while JSON preserved the canonical keyed score. `rivals show` records were 1-0 and 0-1. | PASS |
| Direct recap contract | Summary says `official=false`, `ranked=false`, `affects_elo=false`, and play money only. Methodology states best-of-five heads-up PLHE, 10,000 starting chips each game, bankruptcy wins a game, first to three wins the series, blinds start 50/100 and double every 10 hands before sudden death. | PASS |
| Elo invariance | At `03:03:47Z`, both CLI status and the public leaderboard remained exactly 1,220 and 1,180 on official run `run_eeac5ef66e0f6085`. | PASS |

## Accessibility and keyboard assertions

- The completed challenge's `Open` and `View recap` controls opened an accessible `Match recap` container with heading `Match recap`, ID `match-recap-title`, and a focused `Close` button.
- The result notification could be activated with Enter to open the recap.
- Every highlighted hand was exposed as a link with an accessible description including the hand number, winner, and `Open replay`.
- From the focused Close button, one Tab moved focus to the first Open replay link. Enter navigated to the hand replay page.
- On replay, the accessibility tree announced `SMALL BLIND` and `BIG BLIND` with player names and chip amounts. The checked hand showed a 200-chip small blind and 400-chip big blind at its escalated level.
- The replay's `Back to Rivals` link was keyboard reachable and Enter restored the same Match recap.
- Escape closed the recap and removed the `result` query parameter. With Close focused, Enter also closed it. Both close paths left the underlying rival context available.

Result: PASS. The Match recap surface and Open replay links were discoverable to accessibility APIs and operable by keyboard.

## Preserved evidence and exact files

Evidence root: `/Users/sethsaperstein/Documents/AlphaSchool/alpha-poker-competition/qa/COMPETITION_E2E_FRICTION_PASS7_ARTIFACTS`

Training:

- `a-training/alpha-poker-training-trn_2c02f756a4fe9839.zip`, SHA-256 `ebb7f4b41d20abb4277befa4f5b9c238d5ad1dcb991eed25f051c709ee3cc2f3`
- `b-training/alpha-poker-training-trn_3637aa710d131816.zip`, SHA-256 `bb666f21a3e18511e4a2ed1ff48d23b63c33d760b47869d3708df906e79d13e5`
- Each contains exactly `summary.json`, `events.jsonl`, and `hands.jsonl`.

Official:

- `a-official/sub_25e890f7a75012a2-validation.txt`
- `b-official/sub_2d7b34e0dcbaf4f8-validation.txt`
- `a-official/run_eeac5ef66e0f6085-official-logs.zip`
- `b-official/run_eeac5ef66e0f6085-official-logs.zip`
- Official ZIP SHA-256: `948b49e43bc5d9417f54836457ab221894698906564145c8925d548be7f6f377`
- Each official ZIP contains exactly `result.txt`, `summary.json`, `hands.jsonl`, and `hands.phhs`.

Direct challenge:

- `a-rival-human/alpha-poker-rival-ch_866c565c7ed7038b.zip`
- `a-rival-agent/alpha-poker-rival-ch_866c565c7ed7038b.zip`
- `a-rival-json/alpha-poker-rival-ch_866c565c7ed7038b.zip`
- `b-rival-human/alpha-poker-rival-ch_866c565c7ed7038b.zip`
- `b-rival-agent/alpha-poker-rival-ch_866c565c7ed7038b.zip`
- `b-rival-json/alpha-poker-rival-ch_866c565c7ed7038b.zip`
- All six ZIPs are byte-identical with SHA-256 `058f2b84c4a8153c86dc1f89c9c6876954ccd9b16797859922530ce48ab2b93f`.
- Each contains exactly `result.txt`, `summary.json`, `hands.jsonl`, and `hands.phhs`.

No credential file was copied into the evidence bundle.

## Issue by severity

### Medium

1. The losing-side result notification used an irrelevant zero-chip margin instead of the series score.

   The recipient notification read `pass7ace0907 beat you by 0 play chips` for a 3-1 tournament series. This is the first completion message presented to the losing participant and gives the wrong outcome measure for a best-of-five challenge. The challenge list, status, recap, and artifacts all reported the correct 3-1 result, so recovery was possible, but the notification itself failed the end-to-end acceptance assertion. Expected: winner-first series wording such as `pass7ace0907 beat you 3-1`.

### High, critical, or additional issues

None.
