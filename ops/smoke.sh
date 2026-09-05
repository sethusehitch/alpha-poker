#!/bin/sh
set -eu

project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
base_url="${ALPHA_POKER_BASE_URL:-http://localhost:${ALPHA_POKER_PORT:-8080}}"
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

curl --fail --silent --show-error --max-time 10 "$base_url/ops/healthz" > "$tmp_dir/proxy-health"
curl --fail --silent --show-error --max-time 15 "$base_url/" > "$tmp_dir/home"
curl --fail --silent --show-error --max-time 10 "$base_url/api/health" > "$tmp_dir/api-health"
curl --fail --silent --show-error --max-time 10 -D "$tmp_dir/api-docs-headers" "$base_url/docs" > "$tmp_dir/api-docs"
curl --fail --silent --show-error --max-time 10 "$base_url/openapi.json" > "$tmp_dir/openapi.json"

if ! rg -qi '<!doctype html|<html' "$tmp_dir/home"; then
  echo "Homepage did not return HTML" >&2
  exit 1
fi

if ! rg -q 'Swagger UI' "$tmp_dir/api-docs"; then
  echo "API documentation did not return Swagger UI" >&2
  exit 1
fi

if ! rg -qi '^content-security-policy:.*https://cdn\.jsdelivr\.net' "$tmp_dir/api-docs-headers"; then
  echo "API documentation CSP does not permit its Swagger UI assets" >&2
  exit 1
fi

python3 -c 'import json,sys; document=json.load(open(sys.argv[1])); assert "/v1/account/status" in document["paths"]' "$tmp_dir/openapi.json"

node "$project_dir/ops/smoke-websocket.mjs" "$base_url"

echo "Smoke tests passed for $base_url"
