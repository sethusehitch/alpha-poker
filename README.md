# Alpha Poker

Alpha Poker is a local-first, private, play-money arena for autonomous heads-up Texas Hold'em bots.

The prototype has one league with username and password accounts. Each participant may have one active bot. Official runs use deterministic best-of-five heads-up Pot-Limit Hold'em tournament series and publish chess-style Elo plus win-loss records.

## What is included

- Minimal landing page with a live leaderboard above the instructions
- Downloadable `alpha-poker-starter.zip`
- Copyable Claude, ChatGPT, or Codex build prompt
- Dependency-free Python CLI with account, `validate`, `train`, `submit`, `status`, and `logs` commands
- Heads-up Pot-Limit Texas Hold'em tournament engine with persistent stacks and escalating blinds
- Best-of-five official series, with one chess-style Elo update per series
- FastAPI and SQLite backend
- Salted scrypt passwords and revocable 30-day sessions
- Direct ZIP submission and atomic active-bot replacement
- Serialized, coalescing all-vs-all league reruns after accepted uploads
- Real training WebSocket against a frozen copy of the current leader
- Plain-text, JSON, JSONL, and PHH-style ZIP evidence artifacts
- Isolated bot subprocesses with resource and capability limits
- Persistent league queue recovery, bounded hand logs, artifacts, and upload ZIPs
- Docker and Caddy single-box configuration
- `/feature-requests` community idea board with voting and a six-stage
  lifecycle (`submitted` → `under_review` → `planned` → `in_progress` →
  `shipped`, or `declined`)
- Global feedback widget and a `/contribute` page backed by live, cached
  GitHub issue and pull-request data

## Run locally

Terminal 1, API:

```bash
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python run.py
```

Terminal 2, website:

```bash
npm install
npm run dev
```

Open `http://localhost:3001`. API documentation is at `http://localhost:8000/docs`.
The checked-in platform reference is in [`API.md`](API.md), and the bot contract
is in [`starter-kit/API.md`](starter-kit/API.md).

The website keeps its preview leaderboard if the API is offline and replaces it with live data when the API is available.

## Build and submit a bot

```bash
python3 -m venv .cli-venv
. .cli-venv/bin/activate
pip install -e ./cli
alpha-poker register maya
alpha-poker validate ./starter-kit
alpha-poker submit ./starter-kit
alpha-poker status
alpha-poker logs --output ./alpha-poker-logs
alpha-poker train ./starter-kit --hands 100
```

Set `ALPHA_POKER_API_URL` to use a different API base. The browser keeps its
session in an HTTP-only same-site cookie. The CLI keeps its revocable token in
a local mode-`0600` file, never in the bot package.
Set `ALPHA_POKER_INVITE_CODE` on the server to require a shared cohort code for
new accounts, then register with `--invite-code CODE`.
Set `ALPHA_POKER_OPERATOR_TOKEN` to enable operator-triggered manual league runs.
Set `ALPHA_POKER_OPERATOR_USERNAMES` to a comma-separated list of accounts
allowed to moderate feature requests (change status, hide/restore) and to
promote an approved one to a GitHub issue with `ALPHA_POKER_OPERATOR_TOKEN`.
Set an optional server-only `GITHUB_TOKEN` to raise `/contribute`'s GitHub
rate limit and enable promotion; it is read only on the server and never sent
to the browser. See [`API.md`](API.md) for the full community API surface.

## Run an official local league

Accepted uploads automatically queue a best-of-five league once at
least two bots are active. Uploads arriving during a run are coalesced into one
fresh follow-up run. To request a larger or reproducible run manually:

```bash
curl -X POST http://localhost:8000/v1/admin/runs \
  -H 'content-type: application/json' \
  -H 'authorization: Bearer YOUR_TOKEN' \
  -H 'x-alpha-operator: YOUR_OPERATOR_TOKEN' \
  -d '{"seed": 240904}'
```

Read results from `/v1/leaderboard`, `/v1/matchups`, and `/v1/runs`.

## Single-box containers

The production-shaped local topology is Caddy, the web app, FastAPI, SQLite, and one persistent data volume:

```bash
./ops/up.sh
./ops/smoke.sh
```

Open `http://localhost:8080`. This Mac currently needs the Docker Compose v2 plugin for `ops/up.sh`; both images and the exact topology have also been verified with direct Docker containers in a 4 GB local VM.

## Hosted prototype

The Terraform-managed 4 GB AWS Lightsail prototype is live at
`https://alphapoker.io`, with `https://alpha-poker.32.186.80.108.sslip.io` kept
as a transition fallback. It uses automatic HTTPS, a static IP, daily Lightsail
snapshots, persistent Docker volumes, and restricted SSH.
Deployment and recovery commands are documented in [`HOSTING.md`](HOSTING.md).

## QA

```bash
npm run qa
```

This runs the frontend build, rendered HTML checks, container configuration checks, lint, backend and engine tests, CLI tests, compile checks, and a deterministic starter-kit rebuild.

Browser and full live API, upload, league, training, artifact, and container smoke tests are documented in `QA.md`.

## Open source and community

Alpha Poker is released under the [MIT License](LICENSE). Start with
[CONTRIBUTING.md](CONTRIBUTING.md), follow the
[Code of Conduct](CODE_OF_CONDUCT.md), and report vulnerabilities privately as
described in [SECURITY.md](SECURITY.md). Public bugs and larger feature ideas
belong in GitHub Issues; quick product feedback and community voting are also
available at `/feature-requests` and from the feedback button on every page.

Every change to `main` goes through a pull request, the `qa` check, resolved
review conversations, and a maintainer-controlled merge. Force pushes and
branch deletion are disabled.

## Deferred intentionally

- Password recovery and invitation administration
- Multiple rooms
- Remote Terraform state
- Hostile-code-grade microVM or container isolation

The container layout is sized for the 4 GB Lightsail plan when local QA is complete.
The expected first-host bill and 20-participant workload assumptions are in
[`HOSTING.md`](HOSTING.md).
