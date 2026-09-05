# Alpha Poker platform API

Version: `v1` prototype
Bot schema: `2026-09-01`
Local base URL: `http://localhost:8000/v1`
Hosted base URL: `https://alphapoker.io/v1`

Alpha Poker has one private, play-money league. Mutating and account-owned
routes use revocable bearer sessions. Interactive OpenAPI docs are
available at `http://localhost:8000/docs` locally and
`https://alphapoker.io/docs` on the hosted prototype.
The landing page and completed competition results are intentionally public;
accounts gate joining, submissions, training, and other mutations.

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Process health check |
| `POST` | `/v1/auth/register` | Create an account and session |
| `POST` | `/v1/auth/login` | Create a session for an account |
| `GET` | `/v1/auth/me` | Resolve the current bearer session |
| `POST` | `/v1/auth/logout` | Revoke the current session |
| `GET` | `/v1/account/status` | Participant submission, league state, progress, result, and log URLs |
| `GET` | `/v1/league` | League format, rules, and active-bot count |
| `GET` | `/v1/leaderboard` | Latest completed official standings |
| `GET` | `/v1/matchups` | Latest run's head-to-head summaries |
| `GET` | `/v1/runs` | List official runs |
| `GET` | `/v1/runs/{run_id}` | Run status and reproducibility metadata |
| `GET` | `/v1/runs/{run_id}/matchups` | Matchups for one run |
| `GET` | `/v1/runs/{run_id}/summary` | Winner explanation and per-bot style summary |
| `POST` | `/v1/admin/runs` | Operator-only manual official run |
| `POST` | `/v1/submissions` | Upload and validate a bot ZIP |
| `GET` | `/v1/submissions/current` | Get one user's active bot |
| `GET` | `/v1/submissions/{submission_id}` | Poll validation status |
| `GET` | `/v1/submissions/{submission_id}/logs` | Read validation logs |
| `GET` | `/v1/hands/{hand_id}` | Download one JSON hand record |
| `GET` | `/v1/hands/{hand_id}/phh` | Download one Poker Hand History record |
| `GET` | `/v1/runs/{run_id}/artifacts` | Download all run artifacts as ZIP |
| `POST` | `/v1/training/sessions` | Open a session against the current leader |
| `GET` | `/v1/training/sessions/{session_id}` | Inspect a training session |
| `DELETE` | `/v1/training/sessions/{session_id}` | Stop a training session |
| `GET` | `/v1/training/sessions/{session_id}/artifacts` | Download training logs |
| `WS` | `/v1/training/ws` | Play training hands against the frozen leader |

## Submit a bot

Register once. Login returns the same response shape.

```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H 'content-type: application/json' \
  -d '{"username":"maya","password":"a-long-local-password","invite_code":"optional-cohort-code"}'
```

The response contains a 30-day bearer token. Passwords are stored as salted
scrypt hashes, and only a SHA-256 digest of the session token is stored. Send
the raw token in `Authorization: Bearer TOKEN`. Logging out revokes it.
When `ALPHA_POKER_INVITE_CODE` is set, registration requires the matching code.

Use multipart form data. ZIP files are limited to 2 MB.

```bash
curl -X POST http://localhost:8000/v1/submissions \
  -H 'Idempotency-Key: maya-pressure-v4' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -F 'username=maya' \
  -F 'bot_name=PressureBot' \
  -F 'package=@alpha-poker-submission.zip;type=application/zip'
```

The response is `202 Accepted` with a submission object. Poll its URL until
`status` becomes `accepted` or `rejected`.

For the participant's complete view, request `GET /v1/account/status`. Its
`league.queue.state` is one of `idle`, `waiting_for_players`, `queued`,
`running`, `completed`, or `failed`. Running responses include completed and
total head-to-head matchups. A waiting response includes the current and
minimum active-bot counts. A completed participant result includes its rank,
Elo, record, and `artifacts_url`.

```json
{
  "submission_id": "sub_abc123",
  "username": "maya",
  "bot_name": "PressureBot",
  "status": "accepted",
  "active": true,
  "error": null
}
```

A newly accepted upload atomically replaces that username's prior active bot
and queues a serialized all-vs-all league run once two bots are active.
Uploads arriving while a league is running are coalesced into one follow-up run.
A rejected upload leaves the prior bot active. The server checks ZIP safety,
manifest fields, importability, the 250 ms decision deadline, and the public
action contract. See `starter-kit/API.md` for the bot state and action schema.
Accepted bots execute in isolated Python subprocesses with a clean environment,
bounded memory and output, and blocked host-file, network, shell, and
child-process capabilities. This is intended for a trusted cohort, not hostile
public code. Rejected and inactive upload ZIPs are removed when no current run,
published leader, or nonexpired training session still needs them. Submission
metadata remains available for auditability.

## Run the league

The hand count is per head-to-head pairing and must be even because deals are
mirrored with seats reversed.

```bash
curl -X POST http://localhost:8000/v1/admin/runs \
  -H 'content-type: application/json' \
  -H 'authorization: Bearer YOUR_TOKEN' \
  -H 'x-alpha-operator: YOUR_OPERATOR_TOKEN' \
  -d '{"hand_count_per_pairing": 2000, "seed": 424242}'
```

Manual runs are disabled when authentication is enabled unless the server has
`ALPHA_POKER_OPERATOR_TOKEN` configured and the request sends its exact value in
`X-Alpha-Operator`. Normal cohort uploads need no operator credential and still
schedule official runs automatically.

This returns a `run_id`. Poll `GET /v1/runs/{run_id}`. Once completed, use the
leaderboard, matchup, hand, and artifact endpoints. Reusing the same active bot
packages, rules version, hand count, and seed reproduces the deal schedule and
results.

Leaderboard entries contain the public ranking fields `rank`, `username`,
`bot_name`, `elo_rating`, `matchup_wins`, `matchup_losses`, and `matchup_draws`.
Every new bot version starts at 1,200 Elo. One complete heads-up round robin is
treated as a single, order-independent rating period with K=32; a win is based on
positive total chips across that matchup's mirrored deals. Reusing the exact same
active submission carries its rating into the next league, while replacing the bot
starts the new version at 1,200.

The response also retains the technical analysis fields `bb_per_100`,
`confidence_95`, and `hands` for agents and downloaded reports. Confidence
intervals are computed from hand-level profits while keeping each mirrored deal
pair in the same statistical cluster. These fields are intentionally omitted from
the public landing-page leaderboard.

## Download hand logs

```bash
curl -OJ http://localhost:8000/v1/runs/run_abc123/artifacts
```

The ZIP contains:

- `hands.jsonl`: complete machine-readable action histories
- `hands.phh`: lightweight PHH-style hand summaries
- `hands.csv`: one summary row per hand
- `manifest.json`: run seed, versions, status, and timestamps
- `summary.json`: plain-language winner explanation, uncertainty note, per-bot
  win types, and action counts

Completed runs are archived before detailed hand rows exceed the configured
retention window. The newest 30 run ZIPs remain downloadable after individual
hand rows are removed from SQLite. Older artifact requests return HTTP 410.

## Train against the leader

Create a session:

```bash
curl -X POST http://localhost:8000/v1/training/sessions \
  -H 'content-type: application/json' \
  -H 'authorization: Bearer YOUR_TOKEN' \
  -d '{"username":"maya","opponent":"leader","hand_limit":100,"client_schema_version":"2026-09-01"}'
```

The response includes a short-lived `training_token` and a `websocket_url`.
The current leader's active package is frozen for the lifetime of the session,
so a later upload cannot change the opponent midway through training.

Connect to the returned WebSocket URL. The server emits sequenced messages such
as `connection.ready`, `session.started`, `hand.started`, `action.observed`,
`action.requested`, `action.accepted`, `hand.completed`, and
`session.completed`.

For each `action.requested`, reply before the deadline:

```json
{
  "type": "action.submit",
  "client_action_id": "unique-action-id",
  "hand_id": "copy-from-request",
  "turn_id": "copy-from-request",
  "turn_token": "copy-from-request",
  "action": "raise",
  "amount": 400
}
```

`client_action_id` makes retries idempotent. A stale turn is rejected without
changing the hand. An illegal action or timeout forfeits that hand. Reconnect
with `after_seq={last_seen_seq}` to replay later events, or send
`{"type":"resync.request"}` for a state snapshot. Send
`{"type":"session.stop"}` to stop cleanly.

The supported CLI implements this protocol:

```bash
alpha-poker train ./my-bot --hands 100
```

## Errors

REST errors use a stable envelope:

```json
{
  "error": {
    "code": "submission_not_found",
    "message": "Submission not found"
  }
}
```

## Prototype boundary

The API now provides accounts, revocable sessions, ownership checks, subprocess
resource limits, persistent scheduling, and bounded detailed-log retention. It
still omits password recovery, per-person invitations, rate limiting, and hostile-code-grade
kernel isolation. Do not expose it to arbitrary public uploads. See
`THREAT_MODEL.md` for the exact boundary.
