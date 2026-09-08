# Alpha Poker Competition E2E Friction Pass 12

Date: 2026-09-07 Pacific

Overall result: **FAIL**

This was a black-box release verification against the local web app and public API using a newly downloaded starter kit. No product source was inspected and no product code was modified.

## Targeted release checks

| Check | Result | Evidence |
| --- | --- | --- |
| Homepage leaderboard header contrast | PASS | Computed styles for Rank, Bot, Player, Elo, and Record were `rgb(100, 107, 118)` on white. Each measured **5.38:1**, above the WCAG AA 4.5:1 threshold for normal text. |
| Completed showdown replay | PASS | A completed direct challenge was opened as a participant. Highlighted hand 93 visibly named both players, showed both revealed hole-card sets (`Ad Ah` and `6c Jd`), and showed both evaluated categories (`one_pair` and `straight`). |
| Recap dialog accessibility and focus | PASS | The recap is a `role="dialog"` element with `aria-modal="true"` and `aria-labelledby="match-recap-title"`, resolving to the accessible name "Match recap." Initial focus moved to Close. Shift+Tab from Close wrapped to the last replay link, and Tab wrapped back to Close. Escape closed the recap and returned focus into the still-open, correctly named underlying rival dialog. |
| Pending challenge one-second wait | **FAIL** | Agent output correctly reported `status=pending`. Human output first said the challenge was pending, but then printed **"Still running after 1 seconds."** A pending request has not started and must say it is pending or waiting for the other player, never that it is still running. |

## Starter kit and workflow smoke

- Homepage Copy instructions changed to Copied and exposed a "Prompt copied to clipboard" status message. The copied prompt selected the newest browser-downloaded starter archive and its required `README.md`, `WORKFLOWS.md`, `API.md`, and `cli/` content was present and readable.
- The bundled dependency-free CLI installed in an isolated virtual environment. Top-level, validation, training, rivalry, status, and recap help surfaces loaded successfully.
- Local validation passed with "Bot check passed" and "Ready to train or compete."
- A 400-hand practice run completed. Its ZIP contained `summary.json`, `events.jsonl`, and `hands.jsonl`; the summary reported `status: completed` and `hands_played: 400`.
- Two disposable participant bots were accepted. The official league completed, CLI status reported rank, Elo, and win-loss results, and the signed-in My Bot page visibly showed the completed official result plus validation and latest-result log links.
- A best-of-five direct challenge completed 3-2 over 265 hands. Challenge status and recap output were exercised in human, agent, and JSON modes.
- The downloaded rivalry recap contained exactly four files: `result.txt`, `summary.json`, `hands.jsonl`, and `hands.phhs`.

## Release decision

Do not mark this build PASS. Fix the pending wait timeout copy so a pending request says it is waiting for the other player and never uses "still running." Re-run the one-second human-mode wait check after the fix. All other targeted checks in this pass succeeded.
