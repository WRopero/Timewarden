#!/usr/bin/env bash
# Generates deploy/docker/.env (outside of Git) with random secrets.
# Idempotent: does not overwrite existing values.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/deploy/docker/.env"
TOKEN_FILE="$HOME/.cognee-plugin/observer/token"

touch "$ENV_FILE"; chmod 600 "$ENV_FILE"
get() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true; }
put() { [ -n "$(get "$1")" ] || echo "$1=$2" >> "$ENV_FILE"; }

put AGENTS_PG_PASSWORD "$(openssl rand -hex 24)"
put COGNEE_USER_EMAIL "memory@agents-memory.dev"
put COGNEE_USER_PASSWORD "$(openssl rand -hex 20)"
put COGNEE_JWT_SECRET "$(openssl rand -hex 32)"

# The observer token is created by the plugin; it is always synced.
if [ -s "$TOKEN_FILE" ]; then
  grep -v '^OBSERVER_TOKEN=' "$ENV_FILE" > "$ENV_FILE.tmp" || true
  echo "OBSERVER_TOKEN=$(tr -d '\n' < "$TOKEN_FILE")" >> "$ENV_FILE.tmp"
  mv "$ENV_FILE.tmp" "$ENV_FILE"; chmod 600 "$ENV_FILE"
else
  echo "Missing $TOKEN_FILE: start the observer first (scripts/observer.sh start)" >&2; exit 1
fi
echo "OK: $ENV_FILE"
