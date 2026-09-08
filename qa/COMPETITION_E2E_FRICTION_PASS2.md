# Alpha Poker Competition E2E Friction Pass 2

Date: 2026-09-07 Pacific time  
Test type: Independent first-time participant, black-box end-to-end QA  
Website: `http://127.0.0.1:3011`  
API: `http://127.0.0.1:8011/v1`  
Final verdict: **FAIL**

The complete competition journey succeeded, including two accounts, two bots, practice, official round robin, leaderboard agreement, a direct challenge, all recap formats, and the four-file evidence archive. The pass fails because the completed challenge score is wrong in the required human `rivals status` output.

## Scope and isolation

- Used only the visible local website, the starter ZIP downloaded through that website, the bundled CLI and its help, and the isolated local API.
- Did not inspect product source, repository tests, git history, implementation, or other QA reports.
- Did not contact production or `alphapoker.io`.
- Downloaded `/Users/sethsaperstein/Downloads/alpha-poker-starter (17).zip` through the website.
- Extracted it into the fresh temporary workspace `/tmp/alpha-poker-pass2.Cy7oJN`.
- Installed only the bundled CLI in a fresh virtual environment. The package identified itself as `alpha-poker-cli 0.2.0`.
- Used two exact-path isolated CLI profiles. Both credential files were created with mode `0600`. No password, token, invite value, or credential content is included in this report.

## Participants and bots

| Participant | Bot | Strategy | Official result |
| --- | --- | --- | --- |
| `qap2fox907a` | `P2CallFox907` | Check when legal, otherwise call, otherwise fold | Rank 1, 1,220 Elo, 1-0 |
| `qap2owl907b` | `P2FoldOwl907` | Check when legal, otherwise fold | Rank 2, 1,180 Elo, 0-1 |

Both bots passed local validation, including all four contract checks. Slowest reported decisions were 0.19 ms and 0.20 ms.

## Required journey acceptance evidence

### Onboarding, download, install, and help

- The public home page explained the three-step flow and exposed the starter download.
- The browser download completed successfully and produced a ZIP with the expected starter bot, manifest, participant documentation, and bundled CLI.
- The bundled CLI installed successfully into a fresh virtual environment.
- Top-level and relevant subcommand help rendered correctly.
- Practice is named `train` in the CLI. `train --help` clearly states `--hands` accepts 1 through 400 and defaults to 400.
- Safe boundary checks at 0 and 401 were rejected with `Error: --hands must be between 1 and 400`.
- An intentionally invalid `practice` command failed safely and printed the available command list.

### Build, validate, account setup, and practice

- Built two distinct, simple Python bots from the downloaded starter.
- Both bots passed `validate --verbose` locally.
- Created two new, distinct accounts through secure interactive CLI prompts using the disposable cohort invite.
- `whoami` returned the correct participant for each exact-path profile.
- Each bot completed a five-hand hosted practice session against the leader.
- Both practice runs produced uniquely named training log ZIPs in their requested output directories.

### Submission and official two-bot round robin

- First submission was accepted as `sub_2af541c3a70045b7`.
- Before the second bot existed, status correctly said the official league had not started and was waiting for one more active bot.
- Second submission was accepted as `sub_bba0cfa4456d0339`.
- The official two-bot round robin completed as run `run_600553edce638215`.
- Chess-style Elo behaved as expected from a 1,200 baseline: the winner gained 20 points and the loser lost 20 points, for a zero-sum 1,220 and 1,180 result.

### Cross-surface leaderboard agreement

| Surface | Rank 1 | Rank 2 | Result |
| --- | --- | --- | --- |
| Website leaderboard | `P2CallFox907`, `qap2fox907a`, 1,220, 1-0 | `P2FoldOwl907`, `qap2owl907b`, 1,180, 0-1 | Matches |
| Public `GET /leaderboard` | Same, with 255 hands | Same, with 255 hands | Matches |
| CLI `status` and `rivals list --source leaderboard` | Rank 1, 1,220, 1-0 | Rank 2, 1,180, 0-1 | Matches |

- Website login worked for each account using the same credentials as the CLI.
- The first account's My Bot page showed `P2CallFox907`, in the league, run complete, 1,220 Elo, 1-0, rank 1.
- The second account's My Bot page showed `P2FoldOwl907`, in the league, run complete, 1,180 Elo, 0-1, rank 2.

### Direct challenge

- Challenger discovery showed the recipient bot, 1,180 Elo, and a 0-0 direct record before the match.
- Sent challenge `ch_178c8e53f3ddd0ae` from `qap2fox907a` to `qap2owl907b`.
- Recipient human request output included the challenger, both bot names, best-of-five PLHE format, and pending state.
- An accept attempt without confirmation failed safely and printed the full decision context before instructing the agent to rerun with `--yes`.
- Confirmed acceptance moved the challenge from pending to queued.
- Bounded `status --wait --timeout 60` observed running and then completed without exceeding the bound.
- Authoritative result: `qap2fox907a` won 3-0 in 3 games and 275 hands.
- Website challenge history showed Loss, 3-0, best of 5, 275 hands for the recipient. The website recap stated that public Elo was unchanged and exposed focused hand replays.

### Status and recap formats

- `rivals status --format agent` returned stable facts: completed, score 0-3 from the recipient's perspective, 3 games, 275 hands, winner, and artifact URL.
- `rivals status --format json` returned one valid JSON object with the correct participants, bot snapshot names, score map, winner, run ID, game total, hand total, recap URL, and artifact URL.
- `rivals recap --format human` clearly stated `P2CallFox907 defeated P2FoldOwl907 3-0`, 275 hands across 3 games, and understandable highlight guidance.
- `rivals recap --format agent` returned stable facts plus a quoted result summary.
- `rivals recap --format json` returned one valid JSON object with challenge, matchup, summary, methodology, outcome, and best-hand data.
- The only failed format is the human status score described below.

### Recap evidence archive

Downloaded:

`/tmp/alpha-poker-pass2.Cy7oJN/artifacts/recap/alpha-poker-rival-ch_178c8e53f3ddd0ae.zip`

The ZIP contains exactly these four files, with no extras:

1. `result.txt`
2. `summary.json`
3. `hands.phhs`
4. `hands.jsonl`

Cross-checks passed:

- `result.txt` exactly matches `summary.json.result_text`.
- Winner is consistently `qap2fox907a` and the readable bot result is `P2CallFox907` over `P2FoldOwl907`, 3-0.
- `summary.json` reports challenge ID `ch_178c8e53f3ddd0ae`, run ID `run_rival_4bf9c3f0989abfb2`, direct-rival kind, non-official, non-ranked, play-money-only, and `affects_elo: false`.
- Game hand totals are 113, 93, and 69. Their sum is 275.
- `hands.jsonl` contains exactly 275 valid JSON records, divided 113, 93, and 69 across games 1, 2, and 3.
- Every JSONL record uses the expected run ID and match ID `run_rival_4bf9c3f0989abfb2_match_1`.
- `hands.phhs` contains exactly 275 unique hand blocks.
- The PHHS and JSONL hand identifier sets are identical.
- First and last identifiers are understandable and correctly encode game and hand: `...-g1-h1` through `...-g3-h69`.
- PHHS is readable poker hand history with variant, blinds, stacks, actions, players, and finishing stacks. JSONL is readable structured evidence with cards, board, events, results, stacks, players, game number, and identifiers.

### Elo isolation after direct challenge

After the direct challenge completed:

- CLI status remained 1,220 and 1-0 for `qap2fox907a`.
- CLI status remained 1,180 and 0-1 for `qap2owl907b`.
- Public API leaderboard remained 1,220 and 1,180 with the same official records.
- Website leaderboard remained rank 1 at 1,220 and 1-0, and rank 2 at 1,180 and 0-1.

Direct challenges therefore did not change official Elo or the official win-loss records.

## Genuine issue

### [Major] Human challenge status reports an impossible 3-3 score to the losing recipient

Reproduction:

1. Complete a direct best-of-five challenge where the logged-in recipient loses 0-3.
2. With the recipient profile, run `alpha-poker rivals status CHALLENGE_ID --format human`.
3. Compare it with the same command in agent and JSON formats, or with human recap and the evidence summary.

Actual human status:

`completed, winner qap2fox907a 3-3`

Expected:

The completed score should be unambiguous and consistent with the selected perspective, such as `winner qap2fox907a 3-0`, or `you lost 0-3` for the recipient.

Why this matters:

- A 3-3 score is impossible in a first-to-three best-of-five series.
- It contradicts agent status (`score=0-3`), JSON status (score map 3-0), human recap (3-0), website history (3-0), and all evidence files.
- Human output is participant-facing and is specifically intended to be understandable without parsing structured data.

Likely display-level boundary: the stored result and all structured output are correct, so the defect appears limited to human status score formatting or perspective conversion.

## Final verdict

**FAIL**

All core actions and artifacts completed successfully, but the required human challenge status output is materially incorrect. This should be fixed and the completed-recipient status case rerun before the journey is accepted as a full pass.
