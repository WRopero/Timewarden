<p align="center"><img src="docs/assets/logo-wordmark.svg" alt="OpenMemory" width="560"></p>

# OpenMemory

**Memoria persistente, verificable y local para agentes de código (Claude Code), con OpenSpec como director de cada cambio.**

OpenMemory convierte un repositorio en un proyecto que *recuerda*: al abrir una sesión el agente ya sabe el objetivo, las decisiones vigentes, qué está desplegado y qué no (por rama), qué vulnerabilidades hay abiertas y en qué quedó el último trabajo. Para lo que no está en ese resumen, consulta una memoria semántica que corre **en tu propio equipo** (Docker), sin costo por consulta.

> Se instala solo: le pasas la carpeta a un agente, él detecta el tipo de proyecto (dbt, Dataform, Snowflake, BigQuery, aplicación web…), **te pregunta lo que sea ambiguo** y deja todo listo. Ver [`seed-bundle/AGENT_PROMPT.md`](seed-bundle/AGENT_PROMPT.md).

## Qué obtienes

| Capacidad | Qué hace | Cuesta tokens |
|---|---|---|
| **Briefing de arranque** | Un hook inyecta ~1 500 tokens: objetivo, decisiones, reglas, pendientes, despliegues, seguridad, cambios activos de OpenSpec y el checkpoint de la rama actual | No (determinista, sin LLM) |
| **Recuperación semántica** | Skill `project-memory-recall` + MCP: busca en la memoria por fragmentos, aislada por proyecto | No (embeddings locales) |
| **Checkpoint por rama** | Al cerrar/compactar guarda rama, HEAD, cambios sin commit y últimos pedidos | No |
| **Registro de despliegues** | Qué commit está en cada entorno, cuántos commits faltan y si la rama actual está integrada/desplegada | No |
| **Versiones y seguridad** | Inventario de dependencias, historial (`security` vs `upgrade`), auditoría de vulnerabilidades (OSV) lanzada sola al abrir sesión y pendientes visibles | No |
| **OpenSpec dirige los cambios** | Regla obligatoria: propuesta → revisión → implementación → archivo; los specs también se indexan en la memoria | Solo al indexar |
| **Perfiles de datos** | Reglas especializadas para dbt + Snowflake, Dataform + BigQuery, BigQuery/Terraform, apps web | No |
| **Panel Management Memory** | Tablero de solo lectura: salud, vectores, grafo, PostgreSQL, tokens/costo, uso de la memoria | No |

Indexar documentos nuevos sí consume la suscripción de Claude (≈ 2 llamadas por fragmento); consultar no.

## Instalación en 4 comandos
```bash
cd OpenMemory
seed-bundle/seed.sh doctor                                   # requisitos
seed-bundle/seed.sh machine --yes                            # una vez por equipo (Docker + observer)
seed-bundle/seed.sh project /ruta/al/repo mi-proyecto --lang auto --profile auto
seed-bundle/seed.sh panel --yes                              # panel en http://127.0.0.1:45876
```
`--lang auto` y `--profile auto` detectan idioma y tipo de proyecto; si no están claros **salen con código 3 para que el agente te pregunte**. Guía completa: [`docs/INSTALL.md`](docs/INSTALL.md) (para el agente: [`seed-bundle/SEED.md`](seed-bundle/SEED.md)).

## Documentación
| Documento | Contenido |
|---|---|
| [`docs/INSTALL.md`](docs/INSTALL.md) | **Cómo instalarlo** paso a paso (con agente o a mano), códigos de salida, otro equipo, actualizar y desinstalar |
| [`docs/COMPONENTS.md`](docs/COMPONENTS.md) | **Para qué es cada cosa**: carpetas, scripts, skills, hooks, contenedores y archivos que se crean |
| [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) | Cómo funciona, con grafos: instalación, ciclo de una sesión, auditoría de seguridad, despliegues, OpenSpec |
| [`docs/DEPENDENCIES.md`](docs/DEPENDENCIES.md) | Todo de lo que depende (imágenes, versiones, herramientas) y qué sale de tu equipo |
| [`docs/DATA_PROJECTS.md`](docs/DATA_PROJECTS.md) | Proyectos de datos: BigQuery, Dataform, Snowflake, dbt |
| [`docs/OPENSPEC.md`](docs/OPENSPEC.md) | Cómo OpenSpec dirige el trabajo y se vincula con la memoria |
| [`docs/SECURITY_AND_PRIVACY.md`](docs/SECURITY_AND_PRIVACY.md) | Privacidad, secretos, superficie de red y prohibiciones |
| [`docs/architecture.md`](docs/architecture.md), [`docs/operations.md`](docs/operations.md), [`docs/continuity.md`](docs/continuity.md), [`docs/token-strategy.md`](docs/token-strategy.md), [`docs/diagrams.md`](docs/diagrams.md) | Arquitectura detallada, operación diaria, continuidad entre sesiones, estrategia de tokens, diagramas |
| [`seed-bundle/spec/`](seed-bundle/spec/Cognee-memory-specification.md) | Especificación técnica completa y tabla de resolución de problemas (§21.7) |

## Requisitos
macOS con Docker Desktop (**única plataforma validada**), Claude Code ≥ 2.1.287 con sesión iniciada, Python 3, git, [OpenSpec](https://github.com/Fission-AI/OpenSpec) y conexión a internet en la primera instalación. Detalle y versiones: [`docs/DEPENDENCIES.md`](docs/DEPENDENCIES.md).

## Desarrollo con OpenSpec
Este repositorio se desarrolla con su propio método: los specs vigentes están en [`openspec/specs/`](openspec/specs/) y cada cambio pasa por `openspec/changes/`.

## Licencia
[MIT](LICENSE). Logo: reloj de arena y línea de tiempo ramificada con el monograma WR; inspirado en la estética retro de «autoridad del tiempo», sin usar ningún material protegido.
