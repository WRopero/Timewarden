#!/usr/bin/env bash
# Disparador BAJO DEMANDA de la medicion del Mac para Management Memory (activacion por socket de launchd).
# launchd escucha 127.0.0.1:8018 sin gastar nada y solo lanza host_stats.py --inetd cuando alguien se conecta
# (el boton «Medir el Mac ahora» del panel); el proceso termina tras responder. Reversible.
# Uso: host_stats_launchagent.sh install|uninstall|status|test
set -euo pipefail
LABEL=com.agents-memory.host-stats
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGDIR="$HOME/.local/share/agents_memory_system"
DOM="gui/$(id -u)"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/host_stats.py"
case "${1:-status}" in
  install)
    PY="$(command -v python3)"; mkdir -p "$LOGDIR" "$HOME/Library/LaunchAgents"
    launchctl bootout "$DOM/$LABEL" 2>/dev/null || true
    cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>-I</string><string>$SCRIPT</string><string>--inetd</string></array>
  <key>inetdCompatibility</key><dict><key>Wait</key><false/></dict>
  <key>Sockets</key><dict><key>Listeners</key><dict>
    <key>SockNodeName</key><string>127.0.0.1</string>
    <key>SockServiceName</key><string>8018</string>
  </dict></dict>
  <key>Nice</key><integer>10</integer>
  <key>StandardErrorPath</key><string>$LOGDIR/host-stats.log</string>
</dict></plist>
PL
    launchctl bootstrap "$DOM" "$PLIST"; echo "instalado (bajo demanda, sin proceso residente): $PLIST"; "$0" status ;;
  uninstall)
    launchctl bootout "$DOM/$LABEL" 2>/dev/null || true; rm -f "$PLIST"; echo "desinstalado" ;;
  status)
    launchctl print "$DOM/$LABEL" 2>/dev/null | grep -E "state =|active count|runs =" || echo "LaunchAgent no cargado"
    pgrep -fl "host_stats.py" || echo "ningun proceso host_stats en ejecucion (correcto: solo corre al medir)" ;;
  test)
    curl -s -m 15 -X POST http://127.0.0.1:8018/ | python3 -c "import sys,json;d=json.load(sys.stdin);print('CPU',d['cpu'],'RAM usada',d['memory']['used'])" ;;
esac
