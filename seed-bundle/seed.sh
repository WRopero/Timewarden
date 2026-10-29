#!/usr/bin/env bash
# Seed bundle: instala la memoria de proyecto (Cognee en Docker) en un Mac y en un repositorio nuevo.
# Pensado para que lo ejecute un agente siguiendo SEED.md. Cada fase es idempotente y reporta OK/FALTA.
#
#   seed.sh doctor                          comprueba requisitos (no cambia nada)
#   seed.sh machine --yes                   levanta observer + stack Docker + llaves (una vez por Mac)
#   seed.sh project <repo> <project_id> [--lang auto|es|en] [--profile auto|<capas>] [--no-openspec] [--no-capture] [--with-plugin]
#                                           instala la memoria en el repo (contrato, hooks, skills, plantillas)
#   seed.sh panel --yes                     levanta Management Memory (incluido en el kit, carpeta panel/) (panel de control, solo lectura)
#   seed.sh verify [<repo>]                 comprobaciones de aceptacion rapidas
# Sale con 3 si el idioma O el tipo de proyecto (perfil: dbt/dataform/snowflake/bigquery/webapp/...) es ambiguo: el agente DEBE preguntar al usuario.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MS="$(cd "$HERE/.." && pwd)"
MM_DIR="${MM_DIR:-$MS/panel}"            # el panel viaja dentro del kit (carpeta panel/); sobrescribible con MM_DIR
MM_REPO_URL="${MM_REPO_URL:-}"            # solo si el kit no trae panel/: URL git de Management Memory
ok() { printf '  \033[32mOK\033[0m     %s\n' "$*"; }
miss() { printf '  \033[31mFALTA\033[0m  %s\n' "$*"; BAD=1; }
BAD=0

doctor() {
  echo "Requisitos (spec 21.1):"
  if [ "$(uname -s)" = Darwin ]; then ok "macOS $(sw_vers -productVersion 2>/dev/null)"; else echo "  --     $(uname -s): NO probado (solo se valido en macOS + Docker Desktop). Continua con cautela y reporta lo que falle; launchd no existe aqui."; fi
  command -v docker >/dev/null && docker info >/dev/null 2>&1 && ok "Docker $(docker info --format '{{.ServerVersion}} · {{.NCPU}} CPU · {{.MemTotal}} B')" || miss "Docker no esta corriendo (abre Docker Desktop)"
  command -v claude >/dev/null && ok "Claude Code $(claude --version 2>/dev/null | head -1) (el plugin pide >= 2.1.287)" || miss "claude no esta en PATH"
  command -v python3 >/dev/null && ok "$(python3 --version)" || miss "python3"
  command -v git >/dev/null && ok "git" || miss "git"
  command -v openspec >/dev/null && ok "OpenSpec $(openspec --version 2>/dev/null | head -1) (dirige las implementaciones)" \
    || miss "openspec no esta instalado: curl -fsSL https://raw.githubusercontent.com/Fission-AI/OpenSpec/main/scripts/binary/install.sh | sh   (revisa el script antes; alternativa: npm i -g @fission-ai/openspec)"
  command -v gh >/dev/null && ok "gh (opcional, para GitHub)" || echo "  --     gh no instalado (opcional)"
  for p in 45873 45874 45875 8017 45876; do
    if lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1; then echo "  --     puerto $p ya en uso (normal si el stack ya corre)"; else ok "puerto $p libre"; fi
  done
  [ -f "$MS/deploy/docker/compose.yaml" ] && ok "kit en $MS" || miss "no encuentro deploy/docker/compose.yaml"
  return $BAD
}

machine() {
  [ "${1:-}" = "--yes" ] || { echo "Esto arranca contenedores y un proceso en el Mac. Repite con --yes tras confirmar con el usuario."; exit 1; }
  doctor >/dev/null || { doctor; exit 1; }
  echo "1/5 observer"; "$MS/scripts/observer.sh" start; "$MS/scripts/observer.sh" probe
  echo "2/5 secretos (deploy/docker/.env, 0600)"; "$MS/scripts/gen_env.sh"
  echo "3/5 stack (la primera vez descarga ~640 MB de embedder: 60-90 s o mas)"
  "$MS/scripts/dc.sh" up -d agents_postgres agents_cognee_api agents_cognee_mcp agents_otel_collector
  for i in $(seq 1 60); do curl -s -m 3 http://127.0.0.1:45874/health | grep -q '"status":"ready"' && break; sleep 5; done
  curl -s -m 3 http://127.0.0.1:45874/health | grep -q '"status":"ready"' && ok "API lista" || { miss "la API no llego a ready (docker logs agents_cognee_api)"; exit 1; }
  echo "4/5 llaves"; python3 -I "$MS/scripts/mint_mcp_key.py" mcp || true
  "$MS/scripts/dc.sh" up -d --force-recreate agents_cognee_mcp
  if [ ! -f "$HOME/.cognee/.env" ]; then   # sin esto la llave quedaria sola y el plugin sin sus topes de costo
    mkdir -p "$HOME/.cognee" && chmod 700 "$HOME/.cognee"
    grep -v -E '^(COGNEE_API_KEY|COGNEE_PLUGIN_DATASET)=' "$MS/config/plugin.example.env" | sed -E 's/[[:space:]]+#.*$//' > "$HOME/.cognee/.env"; chmod 600 "$HOME/.cognee/.env"
  fi
  python3 -I "$MS/scripts/mint_mcp_key.py" plugin || true
  echo "5/5 plugin env (~/.cognee/.env)"
  [ -f "$HOME/.cognee/.env" ] && ok "existe (se respeta; compara con config/plugin.example.env y spec 21.4)" || miss "falta ~/.cognee/.env: copia config/plugin.example.env y ajusta (spec 21.4)"
  echo "persistencia tras reinicios (spec 20/23): LaunchAgent del observer"
  [ "$(uname -s)" = Darwin ] && "$MS/scripts/observer_launchagent.sh" install >/dev/null 2>&1 && ok "LaunchAgent del observer instalado (reversible: observer_launchagent.sh uninstall)" \
    || echo "  --     LaunchAgent no instalado (el plugin cognee-memory aun no esta; reintenta tras 'seed.sh project ... --with-plugin')"
}

project() {
  local repo="${1:?uso: seed.sh project <repo> <project_id> [--lang auto|es|en] [--profile auto|<capas>] [--no-openspec] [--no-capture] [--with-plugin]}" pid="${2:?falta project_id}"; shift 2
  local lang=auto profile=auto osp=yes extra=() plugin=0
  while [ $# -gt 0 ]; do case "$1" in
    --lang) lang="$2"; shift 2 ;; --profile) profile="$2"; shift 2 ;; --no-openspec) osp=no; shift ;; --no-capture) extra+=(--no-capture); shift ;; --with-plugin) plugin=1; shift ;; *) echo "opcion desconocida: $1"; exit 2 ;; esac; done
  curl -s -m 4 http://127.0.0.1:45874/health | grep -q ready || { echo "El stack no responde: ejecuta antes 'seed.sh machine --yes'."; exit 1; }
  # el codigo de salida 3 (idioma ambiguo) se propaga tal cual: el agente debe preguntar al usuario
  python3 -I "$MS/scripts/install_project.py" "$repo" --project-id "$pid" --lang "$lang" --profile "$profile" --openspec "$osp" ${extra[@]+"${extra[@]}"}
  local cmds=("claude plugin marketplace add topoteretes/cognee-integrations"
              "claude plugin install cognee-memory@cognee --scope local"
              "claude mcp add --scope local --transport http agents_cognee http://127.0.0.1:45873/mcp")
  if [ "$plugin" = 1 ]; then
    (cd "$repo" && for c in "${cmds[@]}"; do echo "+ $c"; eval "$c"; done)
  else
    echo; echo "Falta (modifica ajustes globales de Claude Code; ejecuta desde $repo tras confirmar con el usuario):"
    printf '  %s\n' "${cmds[@]}"; echo "  o repite este comando con --with-plugin"
  fi
  echo; echo "Siguiente: redactar docs/agent-memory/project.md y el corpus piloto (skill project-memory-bootstrap), luego:"
  echo "  $MS/scripts/memctl.sh sync $repo           # plan"
  echo "  $MS/scripts/memctl.sh sync $repo --apply   # indexa (~2 llamadas a Claude por chunk)"
}

panel() {
  [ "${1:-}" = "--yes" ] || { echo "Levanta 2 contenedores (panel + proxy de Docker de solo lectura) en 127.0.0.1:45876 y un disparador launchd bajo demanda. Repite con --yes tras confirmar con el usuario."; exit 1; }
  curl -s -m 4 http://127.0.0.1:45874/health | grep -q ready || { echo "El stack no responde: ejecuta antes 'seed.sh machine --yes'."; exit 1; }
  if [ ! -f "$MM_DIR/compose.yaml" ]; then
    [ -n "$MM_REPO_URL" ] || { echo "No encuentro el panel en $MM_DIR (el kit debe traer la carpeta panel/). Define MM_DIR o MM_REPO_URL."; exit 1; }
    [ ! -e "$MM_DIR" ] || { echo "$MM_DIR existe y no es el panel: muevelo o define MM_DIR."; exit 1; }
    echo "clonando Management Memory desde $MM_REPO_URL"; git clone --quiet "$MM_REPO_URL" "$MM_DIR"
  fi
  [ "$(uname -s)" = Darwin ] && "$MS/scripts/host_stats_launchagent.sh" install >/dev/null 2>&1 && echo "disparador bajo demanda del Mac instalado (sin proceso residente)"
  python3 -I "$MS/scripts/usage_scan.py" >/dev/null 2>&1 || true
  (cd "$MM_DIR" && python3 scripts/setup.py && docker compose up -d --build)
  for _ in $(seq 1 15); do curl -s -o /dev/null -m 3 http://127.0.0.1:45876/api/overview && break; sleep 2; done
  curl -s -o /dev/null -w "panel: HTTP %{http_code} en http://127.0.0.1:45876\n" http://127.0.0.1:45876/api/overview
}

verify() {
  local repo="${1:-}"
  echo "Aceptacion rapida (spec 21.5):"
  curl -s -m 4 http://127.0.0.1:45874/health | grep -q ready && ok "Cognee API ready" || miss "Cognee API"
  "$MS/scripts/observer.sh" probe 2>/dev/null | grep -q '"auth": *"ok"' && ok "observer auth ok" || miss "observer"
  docker run --rm curlimages/curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $(cat ~/.cognee-plugin/observer/token 2>/dev/null)" http://host.docker.internal:8017/v1/models 2>/dev/null | grep -q 200 && ok "observer alcanzable desde un contenedor" || miss "observer no alcanzable desde Docker"
  curl -s -m 4 -o /dev/null -w '%{http_code}' http://127.0.0.1:45876/api/overview 2>/dev/null | grep -q 200 && ok "panel Management Memory en :45876" || echo "  --     panel no levantado (opcional: seed.sh panel --yes)"
  if [ -n "$repo" ]; then
    [ -f "$repo/.agent-memory/project.yaml" ] && ok "contrato .agent-memory/project.yaml (idioma: $(grep -E '^language:' "$repo/.agent-memory/project.yaml" | awk '{print $2}' | grep . || echo 'es, por defecto'))" || miss "falta .agent-memory/project.yaml"
    local n; n=$(python3 -I "$MS/scripts/memory_brief.py" "$repo" | python3 -c 'import sys; print(len(sys.stdin.read()))')   # caracteres, no bytes (el tope cuenta caracteres)
    [ "$n" -le 6000 ] && ok "briefing de $n caracteres (tope 6000)" || miss "briefing de $n caracteres (tope 6000)"
    (cd "$repo" && claude mcp list 2>/dev/null | grep -i agents_cognee | grep -qi connected) && ok "MCP agents_cognee conectado" || miss "MCP agents_cognee no conectado"
    "$MS/scripts/memctl.sh" status "$repo" 2>/dev/null | tail -6
  fi
  return $BAD
}

case "${1:-help}" in
  doctor) doctor ;; machine) shift; machine "$@" ;; project) shift; project "$@" ;; panel) shift; panel "$@" ;; verify) shift; verify "$@" ;;
  *) sed -n 2,13p "$0" ;;
esac
