#!/usr/bin/env bash
# Gestiona el observer del plugin Cognee (shim OpenAI -> `claude -p`) en el Mac.
# Escucha en 127.0.0.1:8017; los contenedores llegan por host.docker.internal.
# Uso: observer.sh start|stop|status|probe
set -euo pipefail
PLUGIN_DIR="$(ls -d "$HOME"/.claude/plugins/cache/cognee/cognee-memory/*/ 2>/dev/null | sort -V | tail -1)"
[ -n "$PLUGIN_DIR" ] || { echo "plugin cognee-memory no instalado" >&2; exit 1; }
exec python3 "${PLUGIN_DIR}scripts/claude-observer.py" "$@"
