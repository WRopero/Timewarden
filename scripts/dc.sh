#!/usr/bin/env bash
# Wrapper de docker compose para el stack agents_memory_system.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec docker compose -p agents_memory_system -f "$ROOT/deploy/docker/compose.yaml" --env-file "$ROOT/deploy/docker/.env" "$@"
