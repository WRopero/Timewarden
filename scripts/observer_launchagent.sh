#!/usr/bin/env bash
# Observer LaunchAgent (starts at login and restarts if it dies). Reversible.
# Uso: observer_launchagent.sh install|uninstall|status
set -euo pipefail
LABEL=com.agents-memory.observer
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGDIR="$HOME/.local/share/agents_memory_system"
DOM="gui/$(id -u)"
plugin_dir() { ls -d "$HOME"/.claude/plugins/cache/cognee/cognee-memory/*/ 2>/dev/null | sort -V | tail -1; }
case "${1:-status}" in
  install)
    P="$(plugin_dir)"; [ -n "$P" ] || { echo "plugin cognee-memory no instalado" >&2; exit 1; }
    PY="$(command -v python3)"; CL="$(command -v claude)"; mkdir -p "$LOGDIR" "$HOME/Library/LaunchAgents"
    "$(dirname "$0")/observer.sh" stop >/dev/null 2>&1 || true   # evita dos observers en :8017
    for pid in $(lsof -ti tcp:8017 -sTCP:LISTEN 2>/dev/null || true); do   # a manually started observer may still be alive
      if ps -p "$pid" -o command= | grep -q claude-observer; then kill "$pid"; fi
    done
    for _ in $(seq 1 15); do lsof -ti tcp:8017 -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 1; done
    cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string><string>${P}scripts/claude-observer.py</string><string>serve</string><string>--port</string><string>8017</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$(dirname "$CL"):$(dirname "$PY"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>HOME</key><string>$HOME</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOGDIR/observer-launchd.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/observer-launchd.log</string>
</dict></plist>
PL
    launchctl bootout "$DOM/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$DOM" "$PLIST"; sleep 3; echo "instalado: $PLIST"; "$0" status ;;
  uninstall)
    launchctl bootout "$DOM/$LABEL" 2>/dev/null || true; rm -f "$PLIST"; echo "desinstalado (usa memctl.sh up para arranque manual)" ;;
  status)
    launchctl print "$DOM/$LABEL" 2>/dev/null | grep -E "state =|pid =|last exit" || echo "LaunchAgent no cargado"
    curl -s -m 3 http://127.0.0.1:8017/health | cut -c1-160 || true; echo ;;
esac
