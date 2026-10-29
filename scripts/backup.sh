#!/usr/bin/env bash
# Consistent backup: pg_dump + graph volume (with the API stopped) + sync registry.
# NEVER copies the .env. Destination: ~/.local/share/agents_memory_system/backups/<date>/
# Usage: backup.sh            (stops the API during the backup and resumes it if it was up)
#      backup.sh restore-test <dir>   (restores into disposable containers/volumes and verifies)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; DC="$ROOT/scripts/dc.sh"
DEST_ROOT="$HOME/.local/share/agents_memory_system/backups"
PREFIX=agents_memory_system

if [ "${1:-}" = "restore-test" ]; then
  DIR="${2:?usage: backup.sh restore-test <dir>}"; T=agents_restore_test
  docker rm -f ${T}_pg >/dev/null 2>&1 || true; docker volume rm -f ${T}_graph >/dev/null 2>&1 || true
  docker run -d --name ${T}_pg -e POSTGRES_USER=agents -e POSTGRES_PASSWORD=x -e POSTGRES_DB=agents_memory pgvector/pgvector:pg17 >/dev/null
  until docker exec ${T}_pg pg_isready -U agents -d agents_memory >/dev/null 2>&1; do sleep 1; done; sleep 2
  docker exec -i ${T}_pg pg_restore -U agents -d agents_memory --no-owner < "$DIR/agents_memory.dump"
  echo "restored ds_* schemas:"; docker exec ${T}_pg psql -U agents -d agents_memory -tAc "select count(*) from information_schema.schemata where schema_name like 'ds_%'"
  echo "rows in chunks (all ds_*):"
  docker exec ${T}_pg psql -U agents -d agents_memory -tAc "select coalesce(sum((xpath('/row/c/text()', query_to_xml(format('select count(*) c from %I.%I', table_schema, table_name), false, true, '')))[1]::text::int),0) from information_schema.tables where table_schema like 'ds_%' and table_name ilike '%chunk%'"
  docker volume create ${T}_graph >/dev/null
  docker run --rm -v ${T}_graph:/dst -v "$DIR":/src:ro --user 0 --entrypoint tar pgvector/pgvector:pg17 -xzf /src/graph_data.tgz -C /dst
  echo "restored graph files:"; docker run --rm -v ${T}_graph:/g:ro --entrypoint sh pgvector/pgvector:pg17 -c 'find /g -name "*.lbug" | wc -l'
  docker rm -f ${T}_pg >/dev/null; docker volume rm ${T}_graph >/dev/null; echo "restore-test OK (disposable resources removed)"; exit 0
fi

TS=$(date +%Y%m%d-%H%M%S); OUT="$DEST_ROOT/$TS"; mkdir -p "$OUT"; chmod 700 "$DEST_ROOT" "$OUT"
API_WAS_UP=$($DC ps --status running --services | grep -c '^agents_cognee_api$' || true)
$DC stop agents_cognee_mcp agents_cognee_api >/dev/null 2>&1 || true
$DC up -d agents_postgres >/dev/null; until $DC exec -T agents_postgres pg_isready -U agents -d agents_memory >/dev/null 2>&1; do sleep 1; done
$DC exec -T agents_postgres pg_dump -U agents -d agents_memory -Fc > "$OUT/agents_memory.dump"
docker run --rm -v ${PREFIX}_agents_graph_data:/src:ro -v "$OUT":/dst --user 0 --entrypoint tar pgvector/pgvector:pg17 -czf /dst/graph_data.tgz -C /src .
cp "$HOME/.local/share/agents_memory_system/registry.json" "$OUT/" 2>/dev/null || true
cp "$ROOT/deploy/docker/compose.yaml" "$ROOT/observability/collector.yaml" "$OUT/"
( cd "$OUT" && shasum -a 256 * > SHA256SUMS )
[ "$API_WAS_UP" -ge 1 ] && $DC up -d agents_cognee_api agents_cognee_mcp >/dev/null
echo "backup: $OUT"; du -sh "$OUT"/* | sed "s#$OUT/##"
