# Alpha Poker Competition E2E Friction, Pass 9

## Verdict: FAIL

The two-account black-box workflow completed end to end, but two CLI presentation defects violate explicit release acceptance requirements:

1. A sender cannot see an open outgoing challenge in the normal human or agent `rivals show` output.
2. Completed agent output is not winner-first from the losing account. It reports `score=0-3` alongside the actual winner, while human and JSON output report the actual winner-first 3-0 result.

No passwords, invite material, tokens, or other secrets are included in this report.

## Scope and method

- Tested only the public web app at `http://127.0.0.1:3017`, the starter kit fetched from its public download link, the kit documentation, and the isolated documented CLI API override at `http://127.0.0.1:8017/v1`.
- Did not inspect application source, tests, Git state, databases, or previous reports.
- Fresh accounts: `pass9nova907a` and `pass9orbit907b`.
- Fresh bots: `Pass Nine Pressure` and `Pass Nine Patience`.
- CLI installed from the downloaded kit into an isolated virtual environment. Each account used an isolated CLI credentials file.
- Test window: September 7, 2026, approximately 20:13 to 20:19 PDT.

## Timing and evidence

| Stage | Result | Timing or evidence |
| --- | --- | --- |
| Landing page onboarding | PASS | Public page showed the three-step copy: download the starter ZIP, give it to an agent, enter the arena. Download link resolved successfully. |
| Starter kit | PASS with recovery note | Direct public download returned a 28,471-byte ZIP with `README.md`, `API.md`, `WORKFLOWS.md`, `bot.py`, `bot.json`, and bundled `cli/`. The browser-controlled click did not leave a new file in the instructed Downloads folder, so the same public download URL was fetched with `curl`. This appears test-environment-specific because the URL itself worked. |
| CLI install | PASS | Editable install of bundled CLI `0.2.0` completed in 2.8 seconds. Top-level and relevant command help rendered. |
| Local validation | PASS | Both bots passed all four contract checks. Slowest decision was 0.11 ms. End-to-end validations took 0.091 and 0.081 seconds. |
| Practice | PASS | Each bot completed 10 practice hands against `house-bot`. Practice downloads each contained `summary.json`, `events.jsonl`, and `hands.jsonl`. Runs completed in 0.212 and 0.222 seconds. |
| First submission | PASS | `Pass Nine Pressure` accepted as submission `sub_1b5404a140132eda` in 0.367 seconds. Status correctly said the league was waiting for one more active bot and Elo was not assigned. |
| Second submission | PASS | `Pass Nine Patience` accepted as submission `sub_c94d66c79b958df6` in 0.360 seconds. |
| Official league | PASS | First status check at 20:15:51 PDT reported run complete. `Pass Nine Pressure` ranked first at 1,220 Elo with a 1-0 record. `Pass Nine Patience` ranked second at 1,180 Elo with a 0-1 record. Run: `run_56b41277729b0352`. |
| Official format | PASS | Official JSONL records use `game=PLHE`, `betting_limit=pot_limit`, 10,000-chip starting stacks, and named `small_blind` and `big_blind` events. Three games completed, all won by `pass9nova907a`, for a derived best-of-five sweep of 3-0 across 114 hands. |
| Official artifacts | PASS | Both accounts downloaded the exact documented run ZIP with `result.txt`, `summary.json`, `hands.jsonl`, and `hands.phhs`, plus their own validation text file. The official summary lists Elo methodology: 1,200 start, provisional K 40, established K 20, provisional threshold 10 matches, rating once per completed best-of-five series. |
| Rival discovery and show | PARTIAL | List and show commands produced valid human, agent, and single-object JSON forms. Pending current-challenge visibility failed in human and agent show output, detailed below. |
| Challenge pending state | PASS except show defect | Challenge `ch_4cd94c7bf6ce9640` was created at 20:16:29 PDT as pending, best-of-five PLHE. Sender status human, agent, and JSON showed pending. Recipient incoming requests human, agent, and JSON showed pending. Recipient received a CLI and web notification. |
| Accept and complete | PASS | Recipient accepted at 20:17:20.295 PDT. Server started at 20:17:20.298 and completed at 20:17:20.371, about 76 ms after acceptance. Wait command returned in 0.586 seconds. Winner was `pass9nova907a`, 3-0, 120 hands across three games. |
| Both perspectives | PARTIAL | Human and JSON challenge status and recap were factually correct for both users. Losing-account agent status and recap used viewer-order `score=0-3`, detailed below. |
| CLI completion notifications | PASS | Winner: `You beat pass9orbit907b 3-0.` Loser: `pass9nova907a beat you 3-0.` JSON payloads named the winner and stored the series as 3 to 0. |
| Web completion notifications | PASS | Winner web notification: `You beat pass9orbit907b 3-0`. Loser web notification: `pass9nova907a beat you 3-0`. Both were winner-first. |
| Keyboard recap | PASS | On the losing account, the focused completion notification was activated with Return. The accessible recap announced `pass9nova907a won 3-0`, explained best-of-five PLHE and unchanged Elo, and exposed ten links with names such as `Hand 31 won by pass9nova907a Open replay`. |
| Replay event names | PASS | Opened replay announced `posted the small blind of 400 play chips` and `posted the big blind of 800 play chips`, with visible `SMALL BLIND` and `BIG BLIND` labels. |
| Rival recap artifacts | PASS | Downloaded `alpha-poker-rival-ch_4cd94c7bf6ce9640.zip` contained exactly `result.txt`, `summary.json`, `hands.jsonl`, and `hands.phhs`. |
| Recap methodology | PASS | `summary.json` identifies `direct_rival_challenge`, `official=false`, `ranked=false`, `play_money_only=true`, best-of-five heads-up PLHE, 10,000 chips per game, first to three by bankruptcy, blinds starting 50/100 and doubling every 10 hands into current-stack sudden death, and no Elo effect. |
| Named blind events in evidence | PASS | The 120-hand rival JSONL contained 120 `small_blind` and 120 `big_blind` events. Observed levels: 50/100, 100/200, 200/400, 400/800, and 800/1600. |
| Elo invariance | PASS | Before direct play: 1,220 and 1,180. After direct completion and recap: unchanged at 1,220 and 1,180, with official records still 1-0 and 0-1. |

## Issues

### S2 Major: `rivals show` hides the current pending challenge in human and agent formats

After `pass9nova907a` created the pending challenge, these commands were run from the sender account:

```text
alpha-poker rivals show pass9orbit907b --format human
alpha-poker rivals show pass9orbit907b --format agent
alpha-poker rivals show pass9orbit907b --format json
```

Observed human output:

```text
pass9orbit907b, Pass Nine Patience
Elo: 1,180
Direct challenge record: 0-0
```

Observed agent output:

```text
username=pass9orbit907b
bot_name=Pass Nine Patience
elo=1180
direct_record=0-0
is_nemesis=false
```

Neither mentions an open challenge. JSON for the same call correctly included `current_challenge` with the same challenge ID and `status=pending`.

Impact: the ordinary human and agent rival detail flows can make a sender believe no challenge is open. This fails outgoing pending challenge visibility and encourages a duplicate-send attempt that the server must reject.

Expected: when `current_challenge` is non-null, human and agent show output should include at least the challenge ID, direction, opponent, and current status.

### S2 Major: losing-account agent output reverses the actual winner-first score

The challenge completed with `pass9nova907a` as the winner, three games to zero. From the losing account, human status correctly reported:

```text
completed, winner pass9nova907a 3-0
```

JSON correctly reported:

```json
"winner_username": "pass9nova907a",
"series_score": {"pass9nova907a": 3, "pass9orbit907b": 0}
```

However, losing-account agent status reported:

```text
status=completed
score=0-3
winner=pass9nova907a
```

Losing-account agent recap repeated `score=0-3` while its own `result_text` said `Pass Nine Pressure defeated Pass Nine Patience 3-0.`

Impact: agent consumers see a score whose order conflicts with the named winner and with the human, JSON, web, and notification surfaces. This fails the actual winner-first series score requirement and can produce an incorrect participant recap.

Expected: completed agent status and recap should use winner-first score ordering, or explicitly name score keys. For this match, `score=3-0` must accompany `winner=pass9nova907a` from both accounts.

## Passed acceptance details

- Public onboarding and kit documentation were coherent and enough to operate the full workflow without application internals.
- Registration, isolated profiles, local validation, practice, submit, queue bootstrap, official league completion, and log downloads all worked.
- Official league behavior was heads-up best-of-five PLHE and produced Elo as documented.
- Pending and completed challenge APIs were consistent in JSON.
- Challenge notifications were produced for receipt, win, and loss.
- Web challenge rows, notification text, recap heading/content, and replay links all exposed the actual winner-first 3-0 result to assistive technology.
- Replay pages used named blind events rather than anonymous chip deductions.
- Direct rivalry evidence matched the documented four-file contract and contained correct methodology.
- Direct play did not change either public Elo rating.

## Release recommendation

Do not treat Pass 9 as release-acceptable until both S2 issues are fixed and retested from both winner and loser accounts in all three result formats. The engine, artifacts, web recap, notifications, and Elo isolation otherwise passed this run.
