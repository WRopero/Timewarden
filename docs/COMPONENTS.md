# Para qué es cada cosa

## Estructura del repositorio
| Ruta | Para qué sirve |
|---|---|
| `seed-bundle/` | **Puerta de entrada de la instalación**: `SEED.md` (runbook por fases para un agente), `AGENT_PROMPT.md` (qué pegarle), `seed.sh` (orquestador), `manifest.yaml` (versiones probadas, puertos, fases, prohibiciones, legible por máquina) y `spec/` (especificación técnica) |
| `scripts/` | Toda la lógica; Python con librería estándar y bash (ver tabla abajo) |
| `skills/` | Skills de Claude Code `project-memory-*` (recall, handoff, document, bootstrap, maintain, evaluate). Se enlazan por symlink en cada repo |
| `templates/` | Plantillas es/en: sección de `CLAUDE.md`, decisión, implementación, handoff, proyecto, contrato `project.yaml` |
| `profiles/` | **Perfiles por capas** (dbt, dataform, snowflake, bigquery, webapp, python-lib, generic): reglas inyectadas en `CLAUDE.md` y exclusiones de indexación |
| `deploy/docker/` | `compose.yaml` del stack (Postgres+pgvector, API y MCP de Cognee, collector OTel) e imagen delgada de Cognee con volumen de modelo escribible |
| `observability/` | Configuración del collector OpenTelemetry (mide tokens de Claude Code) |
| `analytics/` | Job opcional (DuckDB) que normaliza telemetría y uso |
| `config/` | `versions.lock` (versiones fijadas con digest), `plugin.example.env` (ajustes del plugin con topes de costo), `projects.example.yaml` |
| `panel/` | **Management Memory**: tablero web de solo lectura (FastAPI + JS sin build) |
| `evals/` | Formato y ejemplo de las preguntas de evaluación de recuperación |
| `docs/` | Esta documentación y los diagramas Mermaid |
| `openspec/` | Specs vigentes y cambios de este mismo proyecto (se desarrolla con OpenSpec) |

## Scripts (`scripts/`)
| Script | Para qué |
|---|---|
| `install_project.py` | Instala la memoria en un repo: contrato, plantillas, `CLAUDE.md`, hooks, skills, OpenSpec. Detecta idioma y perfil y pregunta si es ambiguo |
| `detect_language.py` / `detect_project_type.py` | Detección es/en y de tipo de proyecto (capas) con confianza y evidencias; salida 2 = preguntar al usuario |
| `memory_brief.py` | **Hook `SessionStart`**: arma el briefing (sin LLM) y lanza en segundo plano la auditoría de seguridad |
| `memory_checkpoint.py` | **Hooks `SessionEnd`/`PreCompact`**: escribe el checkpoint de la rama (`handoffs/_local/auto-<rama>.md`) y refresca el uso |
| `memory_deploy.py` | Registro de despliegues por entorno y estado por rama (`record`/`status`) |
| `memory_deps.py` | Inventario de dependencias y runtimes, historial de cambios con motivo y `docs/agent-memory/security/dependencias.md` |
| `memory_audit.py` | Auditoría de vulnerabilidades contra OSV con las versiones exactas de los lockfiles |
| `memory_stale.py` | Detecta documentos de memoria obsoletos comparando sus `source_paths` con Git, sin gastar tokens |
| `sync_markdown.py` | Sincroniza `docs/agent-memory/` y los specs de OpenSpec hacia Cognee (incremental por hash, verifica recuperación) |
| `memctl.sh` | Operación diaria: `up`, `stop`, `status`, `sync`, `eval` |
| `memory_eval.py` | Evalúa recall@5 con preguntas de `evals/` |
| `cognee_adapter.py` | Cliente HTTP de Cognee (add, cognify, search, forget) |
| `observer.sh`, `observer_launchagent.sh` | Observer: puente local que usa tu suscripción de Claude (`claude -p`) para que Cognee resuma e indexe; el LaunchAgent lo mantiene vivo tras reinicios |
| `host_stats.py`, `host_stats_launchagent.sh` | Medición bajo demanda del equipo para el panel (sin proceso residente) |
| `usage_scan.py` | Resume cuándo se usó la memoria (solo metadatos de los transcripts) para el panel |
| `gen_env.sh`, `mint_mcp_key.py`, `dc.sh` | Secretos del stack (0600), llaves de API y wrapper de `docker compose` |
| `claude-memory` | Lanza Claude Code con telemetría OTel para medir tokens |
| `weekly_report.py`, `backup.sh` | Informe semanal de consumo y respaldo/restauración de prueba |
| `install_skills.sh` | Enlaza las skills en el repo y las excluye de Git localmente |

## Lo que se crea en tu repositorio
| Archivo | Versionado | Para qué |
|---|---|---|
| `.agent-memory/project.yaml` | Sí | Contrato: id, idioma, perfil, datasets, fuentes y exclusiones |
| `.agent-memory/local.yaml` | **No** | Ruta del kit en este equipo |
| `.agent-memory/deployments.json` | Sí | Registro de despliegues |
| `.agent-memory/dependencies.json` | Sí | Inventario e historial de versiones |
| `.agent-memory/security-ignore.txt` | Sí (opcional) | Riesgos aceptados |
| `docs/agent-memory/` | Sí | Corpus de memoria en Markdown (fuente canónica; Cognee es solo un índice derivado) |
| `docs/agent-memory/security/dependencias.md` | Sí | Versiones, historial y vulnerabilidades pendientes (generado) |
| `docs/agent-memory/handoffs/_local/` | No | Checkpoints automáticos por rama |
| `CLAUDE.md` (sección) | Sí | Reglas para el agente: consultar ante ambigüedad, OpenSpec obligatorio, despliegues, seguridad y reglas del perfil |
| `.claude/settings.local.json` | No | Hooks (briefing/checkpoint) |
| `.claude/skills/project-memory-*` | No | Symlinks a las skills |
| `openspec/`, `.claude/commands/opsx-*` | Sí | OpenSpec inicializado |

## Contenedores (Docker, solo `127.0.0.1`)
| Contenedor | Puerto | Para qué |
|---|---|---|
| `agents_cognee_api` | 45874 | API de Cognee: ingesta, grafo de conocimiento, búsqueda |
| `agents_cognee_mcp` | 45873 | Servidor MCP que expone `recall` a Claude Code |
| `agents_postgres` | — | PostgreSQL + pgvector: vectores (768 dim) y metadatos, un esquema por dataset |
| `agents_otel_collector` | 45875 | Recoge telemetría de Claude Code para medir tokens |
| `mm_app` + `mm_docker_proxy` | 45876 | Panel Management Memory y proxy de solo lectura al motor de Docker |
Fuera de Docker: el **observer** (127.0.0.1:8017) y los LaunchAgents opcionales. `agents_memory_system` es el nombre interno del proyecto Docker Compose (identifica volúmenes y red).
