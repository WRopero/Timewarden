#!/usr/bin/env bash
# Operations for the memory stack. Usage: memctl.sh <command> [args]
#   up        starts observer + stack (keeps volumes)
#   stop      pauses the stack (NEVER uses down -v)
#   status    real status: containers, API, observer, sync log
#   sync REPO syncs the repo's docs/agent-memory (--apply to execute)
#   eval REPO evaluates retrieval with evals/cases.<project_id>.jsonl
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
    echo; printf 'API:      '; curl -s -m 4 http://127.0.0.1:45874/health || echo "down"; echo
    printf 'Observer: '; "$ROOT/scripts/observer.sh" status 2>/dev/null | tail -1 | cut -c1-200 || echo "down"
    [ -n "${2:-}" ] && python3 -I "$ROOT/scripts/sync_markdown.py" "$2" --status || true ;;
  sync)
    shift; python3 -I "$ROOT/scripts/sync_markdown.py" "$@" ;;
  eval)
    REPO="$2"; PID=$(grep -E '^project_id:' "$REPO/.agent-memory/project.yaml" | awk '{print $2}')
    DS=$(grep -E '^memory_dataset:' "$REPO/.agent-memory/project.yaml" | awk '{print $2}')
    python3 -I "$ROOT/scripts/memory_eval.py" "$ROOT/evals/cases.$PID.jsonl" --dataset "$DS" --project-id "$PID" ;;
  *) sed -n 2,9p "$0" ;;
esac
