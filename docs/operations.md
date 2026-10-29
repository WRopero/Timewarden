# Operaciones

Todo pasa por `scripts/memctl.sh`. Los valores de abajo se verificaron el 2026-10-26.

| Operacion | Comando | Que sigue funcionando |
|---|---|---|
| Arrancar | `memctl.sh up` (observer + stack) | — |
| **Pausar captura** | `COGNEE_CAPTURE=false` en `~/.cognee/.env` (ya es el valor del piloto) | recall y guardado explicito |
| **Desconectar agente** | `claude plugin disable cognee-memory@cognee` y `claude mcp remove agents_cognee` | datos y Markdown |
| **Detener memoria** | `memctl.sh stop` (= `docker compose stop`; **nunca** `down -v`) | el trabajo normal de Claude (probado: sesion de 4,5 s con el stack caido) |
| Estado | `memctl.sh status <repo>` | — |
| Sincronizar | `memctl.sh sync <repo> [--apply]` | — |
| Evaluar | `memctl.sh eval <repo>` | — |
| Backup | `scripts/backup.sh` (para la API un momento) | — |
| Probar restauracion | `scripts/backup.sh restore-test <dir>` | usa recursos desechables |
| Telemetria | `scripts/dc.sh --profile eval run --rm agents_analytics report --project <id>` | — |

## Instalar la memoria en un proyecto nuevo
`scripts/install_project.py <repo> --project-id <id>` (idempotente): contrato `.agent-memory/project.yaml`, esqueleto `docs/agent-memory/`, plantillas, seccion en `CLAUDE.md`, hooks (briefing/checkpoint) en `.claude/settings.local.json`, skills y exclusiones locales de Git. Luego escribir `project.md` y los primeros documentos y `memctl.sh sync <repo> --apply`.

## Observer persistente (LaunchAgent)
`scripts/observer_launchagent.sh install` lo arranca al iniciar sesion y lo reinicia si cae (probado: auth ok bajo launchd, reinicio tras `kill`, accesible desde el contenedor). `status` y `uninstall` lo gestionan. Log: `~/.local/share/agents_memory_system/observer-launchd.log`. Con el agente instalado, `memctl.sh up` no necesita arrancarlo.

## Arranque en frio
1. `scripts/observer.sh start` (el observer es un proceso del Mac; se pierde al reiniciar).
2. `scripts/gen_env.sh` (idempotente; sincroniza el token del observer al `.env`).
3. `scripts/dc.sh up -d` (Postgres → API → MCP, collector).
4. Primera vez: `scripts/mint_mcp_key.py` y reiniciar `agents_cognee_mcp`.

## Verificar que el observer llega desde Docker
`docker run --rm curlimages/curl -H "Authorization: Bearer $(cat ~/.cognee-plugin/observer/token)" http://host.docker.internal:8017/v1/models`

## Telemetria de sesiones
`scripts/claude-memory <project_id> <A|B> -- <args de claude>` exporta OTel al collector (`127.0.0.1:45875`).

## Cosas que NO hacer
`docker compose down -v`, `forget` con `everything`, montar `~/.cognee-plugin/observer/` (contiene el token), exponer puertos fuera de `127.0.0.1`.
