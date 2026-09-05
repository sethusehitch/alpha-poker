#!/bin/sh
set -eu

project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if docker compose version >/dev/null 2>&1; then
  compose() { docker compose "$@"; }
elif command -v docker-compose >/dev/null 2>&1; then
  compose() { docker-compose "$@"; }
else
  echo "Docker Compose v2 is required. Install or enable it, then rerun this command." >&2
  exit 1
fi

compose up --build --detach --wait
echo "Alpha Poker is running at http://localhost:${ALPHA_POKER_PORT:-8080}"
