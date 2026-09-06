# Local single-box stack

This is the deployment shape for the Alpha Poker prototype. It runs locally
first and can later move unchanged to one 4 GB Linux server with Docker Compose.

## Services

- `caddy`: the only public service, on port `8080` by default
- `web`: the vinext site on the private Compose network
- `api`: FastAPI, SQLite, match execution, and training WebSockets
- `alpha_poker_data`: the persistent SQLite, submission, and hand-history volume

Caddy sends `/v1/*`, `/docs`, `/redoc`, and `/openapi.json` to FastAPI. It also
accepts `/api/v1/*` as a convenience alias and removes the `/api` prefix. Every
other path goes to the site. Caddy supports WebSocket upgrades without extra
configuration.

The API deliberately runs as one process with one match at a time. This avoids
SQLite write contention and leaves memory for bot subprocesses on a 4 GB box.

## Start and verify

Docker Desktop or Docker Engine with Compose v2 is required.

```sh
./ops/up.sh
./ops/smoke.sh
open http://localhost:8080
```

`up.sh` creates `.env` from `.env.example` on first run and waits for every
container health check. The smoke test checks Caddy, the homepage, the API, and
a real training WebSocket session. View status and logs with:

```sh
docker compose ps
docker compose logs --follow
```

Stop the stack without removing data:

```sh
./ops/down.sh
```

## Data and reset behavior

Application state lives in the named volume `alpha-poker_alpha_poker_data`.
`docker compose down` preserves it. To inspect or back it up:

```sh
docker compose exec api sh -lc 'find /data -maxdepth 2 -type f -ls'
docker run --rm \
  -v alpha-poker_alpha_poker_data:/data:ro \
  -v "$PWD":/backup \
  alpine tar czf /backup/alpha-poker-data.tgz -C /data .
```

Removing the volume permanently deletes local users, submissions, results, and
hand histories. Do that only when a full local reset is intended:

```sh
docker compose down --volumes
```

## Configuration

Copy `.env.example` to `.env` and adjust values there. Important defaults:

- `ALPHA_POKER_PORT=8080`
- `API_MODULE=app.main:app`
- `API_HEALTH_PATH=/api/health`
- `MATCH_CONCURRENCY=1`
- `ALPHA_POKER_AUTO_RUN=true`
- `ALPHA_POKER_AUTO_RUN_HANDS=200`
- `ALPHA_POKER_AUTO_RUN_TIMEOUT_SECONDS=900`
- `ALPHA_POKER_AUTH_REQUIRED=true`
- `ALPHA_POKER_RETAINED_HAND_RUNS=2`
- `ALPHA_POKER_RETAINED_ARTIFACT_RUNS=30`
- `ALPHA_POKER_INVITE_CODE=` (set this before sharing a hosted cohort)
- `ALPHA_POKER_OPERATOR_TOKEN=` (set this only for operator-triggered manual runs)

The queue state is stored in SQLite. A requested run that was interrupted by an
API restart resumes after startup. Only one league executes at a time, including
manual runs. Completed run ZIPs are written atomically before older detailed
hand rows are pruned.

The browser API base stays `/v1`, which makes development, WebSockets, and a
later domain same-origin. Do not expose ports `3000` or `8000` publicly.

When using the CLI against the container stack, set its API URL to
`http://localhost:8080/v1`.

## Before moving to Lightsail

Keep the same Compose topology on Ubuntu and attach the domain only after local
functional and container QA pass. At that point, change Caddy from `:8080` to
the real hostname, remove `auto_https off`, and publish ports `80` and `443`.
Also add a scheduled encrypted backup of the data volume. No cloud resources are
created by this repository.
# Operations

Local production-shaped stack:

```bash
./ops/up.sh
./ops/smoke.sh
./ops/down.sh
```

AWS Lightsail with an AWS CLI profile:

```bash
AWS_PROFILE=your-profile ./ops/aws/apply-infra.sh
AWS_PROFILE=your-profile ./ops/aws/deploy.sh
```

`apply-infra.sh` provisions or reconciles the 4 GB host, static IP, firewall,
snapshot schedule, and deployment public key through Terraform. `deploy.sh`
uploads a release, rebuilds the containers, waits for health, and performs an
external HTTPS and training WebSocket smoke test. Run `show-access.sh` only
when the cohort invite or operator token is needed.
