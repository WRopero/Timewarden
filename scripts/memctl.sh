#!/usr/bin/env bash
# Operaciones del stack de memoria. Uso: memctl.sh <comando> [args]
#   up        arranca observer + stack (conserva volumenes)
#   stop      pausa el stack (NUNCA usa down -v)
#   status    estado real: contenedores, API, observer, registro de sync
#   sync REPO sincroniza docs/agent-memory del repo (--apply para ejecutar)
#   eval REPO evalua recuperacion con evals/cases.<project_id>.jsonl
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DC="$ROOT/scripts/dc.sh"
case "${1:-help}" in
  up)
    "$ROOT/scripts/observer.sh" start >/dev/null
    "$ROOT/scripts/gen_env.sh" >/dev/null
    "$DC" up -d agents_postgres agents_cognee_api agents_cognee_mcp agents_otel_collector ;;
  stop)
    "$DC" stop ;;
  status)
    "$DC" ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
    echo; printf 'API:      '; curl -s -m 4 http://127.0.0.1:45874/health || echo "caida"; echo
    printf 'Observer: '; "$ROOT/scripts/observer.sh" status 2>/dev/null | tail -1 | cut -c1-200 || echo "caido"
    [ -n "${2:-}" ] && python3 -I "$ROOT/scripts/sync_markdown.py" "$2" --status || true ;;
  sync)
    shift; python3 -I "$ROOT/scripts/sync_markdown.py" "$@" ;;
  eval)
    REPO="$2"; PID=$(grep -E '^project_id:' "$REPO/.agent-memory/project.yaml" | awk '{print $2}')
    DS=$(grep -E '^memory_dataset:' "$REPO/.agent-memory/project.yaml" | awk '{print $2}')
    python3 -I "$ROOT/scripts/memory_eval.py" "$ROOT/evals/cases.$PID.jsonl" --dataset "$DS" --project-id "$PID" ;;
  *) sed -n 2,9p "$0" ;;
esac
