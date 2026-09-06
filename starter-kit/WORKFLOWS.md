# Alpha Poker workflows for coding agents

Hosted API: `https://alphapoker.io/v1`

This guide is for Claude, ChatGPT, Codex, or another coding agent with terminal
access. Explain the workflow to the participant first, then perform it for them.
Do not ask the participant to copy terminal commands when you can run them.

If this guide came from a download, locate the most recently modified file
matching `alpha-poker-starter*.zip` in the participant's Downloads folder.
Names such as `alpha-poker-starter (1).zip` are normal browser duplicates. Tell
the participant which exact archive you selected, extract it to a new folder,
and verify that it contains `README.md`, `WORKFLOWS.md`, `API.md`, and `cli/`
before continuing. Never silently reuse an older extracted copy.

## What you can do

- Build and locally validate `bot.py` and `bot.json`.
- Register or log in to the participant's Alpha Poker account.
- Train locally against the current hosted leader over WebSocket.
- Inspect downloaded training hands and improve the strategy.
- Submit the best version. Each accepted submission replaces the participant's
  one active bot.
- Check submission validation, league-run status, and the leaderboard.
- Download official run artifacts and training hand logs.
- Find classmates by player or bot name and explain their public Elo.
- Send a 200-hand direct challenge after the participant chooses an opponent.
- Check incoming requests and accept or decline after participant approval.
- Wait for a rivalry match, report the winner and play-chip margin, and
  download its recap evidence.
- Read challenge notifications and mark them read after sharing the result.

## Agent-operated setup

Create a local virtual environment and install the bundled dependency-free CLI
from `./cli`. Use the hosted API above with `--api-url` or set
`ALPHA_POKER_API_URL` only for the current process. Never place a password,
invite code, or session token in bot files, shell history, or source control.
Let the CLI request passwords through its secure prompt.

Run `alpha-poker --help` and the relevant subcommand help before operating.
The normal order is account setup, validation, training, strategy iteration,
submission, status checks, then artifact download. Confirm each result for the
participant and continue until the bot is competing or a human-only input is
required.

When choosing a destination for training logs, `alpha-poker train --output`
accepts either a directory or an explicit `.zip` filename. If you provide a
directory, the CLI creates a uniquely named training-log ZIP inside it.

After submitting, run `alpha-poker status` until it reports either a completed
result, a clear wait for another participant, or an actionable failure. Run
`alpha-poker logs --output ./alpha-poker-logs` to download validation output
and the newest official hand-log ZIP when available. The participant can see
the same state by logging in on the website and opening their account.

## Agent-operated rival flow

Rival commands should normally use `--json` so results are reliable to parse.
Present the useful facts conversationally instead of pasting raw JSON.

1. Offer to find a classmate by username or bot name, list prior rivals, or
   browse the leaderboard.
2. Show the selected opponent's bot, Elo, and direct-challenge record. Ask the
   participant whether they want to send the fixed 200-hand challenge.
3. Only after approval, send the challenge with the CLI's `--yes` flag. The
   CLI includes an idempotency key, and the server prevents duplicate open
   challenges.
4. Check requests with `rivals requests`. For an incoming request, explain the
   two current bots before asking whether to accept or decline.
5. Use `rivals status CHALLENGE_ID --wait --json` when the participant wants to
   stay for the result. The wait is bounded. If it times out, explain that the
   match remains safe on the server and can be checked later.
6. On completion, use `rivals recap CHALLENGE_ID --output PATH --json`. Report
   who won and by how many play chips, then offer to inspect selected hands and
   help the participant form a strategy hypothesis.

Useful commands for the coding agent:

```text
alpha-poker rivals list --source leaderboard --json
alpha-poker rivals list --source mine --search maya --json
alpha-poker rivals show maya --json
alpha-poker rivals history maya --limit 20 --json
alpha-poker rivals requests --status incoming --json
alpha-poker rivals challenge maya --yes --json
alpha-poker rivals accept CHALLENGE_ID --yes --json
alpha-poker rivals decline CHALLENGE_ID --yes --json
alpha-poker rivals cancel CHALLENGE_ID --yes --json
alpha-poker rivals status CHALLENGE_ID --wait --json
alpha-poker rivals recap CHALLENGE_ID --output ./rival-recaps --json
alpha-poker notifications list --unread --json
alpha-poker notifications read NOTIFICATION_ID --json
```

Direct rivalry challenges never change public Elo. Their history contains only
explicit challenges, not the many pairings from official round robins. Do not
promise that a challenge has started merely because it was sent: it remains
pending until the recipient accepts, then moves through queued and running.

## Important behavior

- Training keeps the participant's bot local and does not alter standings.
- Submission uploads only `bot.py` and `bot.json`.
- A successful new submission atomically replaces the participant's prior
  active bot.
- Accepted uploads queue a new official league run. The leaderboard refreshes
  after that run finishes.
- A league needs at least two active bots. With only one, status truthfully says
  it is waiting for another participant rather than claiming a run is active.
- Running leagues show completed and total head-to-head matchups. Every run has
  a server-side deadline; failures remain visible and a later accepted upload
  safely retries the queue.
- Training and official-run artifacts contain the hand logs needed for review.
- Rival challenges use current active bots at acceptance, produce their own
  recap evidence, and do not affect the leaderboard.

The bot input and action contract is in `API.md`. CLI details are in
`cli/README.md`. The hosted REST API reference is available at
`https://alphapoker.io/docs`.
