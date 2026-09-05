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

The bot input and action contract is in `API.md`. CLI details are in
`cli/README.md`. The hosted REST API reference is available at
`https://alphapoker.io/docs`.
