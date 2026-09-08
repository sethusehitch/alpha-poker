# Alpha Poker local API

This is the authenticated, single-league prototype API. It stores state in SQLite and bot packages and generated artifacts on the local filesystem.

## Run locally

```bash
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python run.py
```

OpenAPI is available at `http://127.0.0.1:8000/docs`. Override the data location with `ALPHA_POKER_DATA_DIR`. Set `ALPHA_POKER_SEED=false` for an empty database.

The frontend can use `http://127.0.0.1:8000/v1/leaderboard`. Account-owned and
mutating routes require a bearer token by default. Set
`ALPHA_POKER_AUTH_REQUIRED=false` only for isolated development tests. Each
accepted upload queues a serialized round robin of best-of-five Pot-Limit Hold'em tournament series. Set `ALPHA_POKER_AUTO_RUN=false` to make runs manual.

## Test

```bash
.venv/bin/pytest -q
```

## Validation and engine integration

Package validation checks ZIP paths, expanded size, `bot.json`, and `bot.py`. It
then launches the bot in an isolated Python subprocess, calls `decide(state)`
under the 250 ms smoke deadline, and validates the returned public action before
atomically activating the submission. The subprocess has resource limits and
blocks host-file, network, shell, and child-process capabilities. A separate
container or microVM boundary is still required before accepting hostile public
code.

Official runs load accepted bots through this adapter and execute deterministic best-of-five Pot-Limit Hold'em tournament series. Each game has persistent stacks, escalating blinds, and a bankruptcy finish. Training freezes the active submission belonging to the latest leaderboard leader when the session is created. The WebSocket then drives real engine hands and writes actual hand histories to the downloadable training artifact.
