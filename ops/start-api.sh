#!/bin/sh
set -eu

api_module="${API_MODULE:-app.main:app}"

cd /app/server
exec uvicorn "$api_module" \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --proxy-headers \
  --forwarded-allow-ips='*' \
  --no-access-log \
  --log-level "${LOG_LEVEL:-info}"
