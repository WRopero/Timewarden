# Kit de memoria de proyecto (Cognee en Docker + Claude Code)

Instala una memoria persistente y verificable para agentes de código en cualquier repositorio: briefing automático al abrir sesión, recuperación local (embeddings en Docker, sin costo por consulta), checkpoint por rama, registro de despliegues, versiones/seguridad con auditoría automática, indexación de specs de OpenSpec y un panel de control de solo lectura. Incluye **perfiles para proyectos de datos** (dbt + Snowflake, Dataform + BigQuery, BigQuery/Terraform) y de aplicaciones web.

| Contenido | Para qué |
|---|---|
| `AGENT_PROMPT.md` | El mensaje que le pegas a un agente para instalar todo |
| `SEED.md` | Runbook por fases: comando, resultado esperado, cuándo preguntar |
| `../docs/DATA_PROJECTS.md` | Qué cambia en proyectos de datos (BigQuery, Dataform, Snowflake, dbt) |
| `../docs/INSTALL.md` | Instalación paso a paso para personas |
| `seed.sh` | Orquestador: `doctor`, `machine`, `project`, `panel`, `verify` |
| `manifest.yaml` | Versiones probadas, puertos, fases, prohibiciones (legible por máquina) |
| `spec/` | Especificación técnica completa: diseño, replicación (§21), problemas frecuentes |

## Uso rápido
```bash
cd <KIT>
seed-bundle/seed.sh doctor                                    # requisitos
seed-bundle/seed.sh machine --yes                             # una vez por equipo
seed-bundle/seed.sh project /ruta/al/repo mi-proyecto --lang auto --profile auto
seed-bundle/seed.sh panel --yes                               # panel en http://127.0.0.1:45876
seed-bundle/seed.sh verify /ruta/al/repo
```
`--lang auto` y `--profile auto` detectan idioma y tipo de proyecto y, si no están claros, **salen con código 3 para que el agente te pregunte**.

## Requisitos
macOS con Docker Desktop (única plataforma validada), Claude Code ≥ 2.1.287 con sesión iniciada, Python 3, git y conexión a internet para la primera instalación (imágenes Docker, modelo de embeddings ~640 MB, plugin `cognee-memory` del marketplace público de Cognee).

## Privacidad
Todo corre en tu equipo (puertos solo en `127.0.0.1`). Sale a Claude únicamente el texto que se **indexa** y el texto recuperado que lees en la conversación; la auditoría de vulnerabilidades envía a `api.osv.dev` solo nombres y versiones de paquetes. No se guardan credenciales: los perfiles excluyen `profiles.yml`, llaves, cuentas de servicio y estado de Terraform.
