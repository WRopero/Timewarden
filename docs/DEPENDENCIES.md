# Dependencias

## En tu equipo (lo que debes tener)
| Herramienta | Versión probada | Para qué |
|---|---|---|
| macOS + Docker Desktop | Docker Engine 27.5.1, Compose 2.32.4, VM de 8 GB y 8 CPU | Ejecuta el stack. **Única plataforma validada**; en Linux/Windows el instalador avisa y no se garantiza |
| Claude Code | 2.1.311 (mínimo 2.1.287) con sesión iniciada | Agente, hooks, skills y MCP; el observer usa tu suscripción |
| Python 3 | 3.12 | Todos los scripts (solo librería estándar) |
| git | cualquiera reciente | Estado de ramas, frescura, despliegues |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | 1.15.0 | Dirige cada cambio; forma parte de la instalación |
| Internet (primera vez) | — | Imágenes Docker, modelo de embeddings (~640 MB), plugin del marketplace de Cognee |

## Imágenes y componentes (fijados en `config/versions.lock`)
| Componente | Versión | Para qué |
|---|---|---|
| Cognee (API) | 1.6.5 | Ingesta, grafo de conocimiento, búsqueda |
| Cognee MCP | `main-37f788b` | Expone `recall` a Claude Code |
| PostgreSQL + pgvector | pg17 / pgvector 0.8.x | Vectores y metadatos |
| OpenTelemetry Collector | 0.111.0 | Telemetría de Claude Code (tokens) |
| Plugin `cognee-memory` | 1.7.4 | Hooks de captura y skills de Cognee dentro de Claude Code |
| Embeddings | `jinaai/jina-embeddings-v2-base-es` (768 dim, fastembed 0.8.0) | Búsqueda semántica bilingüe **en local**, sin internet ni costo |
| DuckDB (analytics, opcional) | 1.1.3 | Normaliza telemetría y uso bajo demanda |
| Panel: FastAPI / uvicorn / psycopg / httpx | 0.115.6 / 0.32.1 / 3.2.3 / 0.27.2 | Tablero de solo lectura |
| `wollomatic/socket-proxy` | 1.11.0 | Proxy de solo lectura al motor de Docker para el panel |
| Cytoscape.js | 3.30.2 | Dibuja el grafo en el panel (se descarga al construir la imagen) |

Cambiar el modelo de embeddings obliga a reindexar todo: nunca se mezclan vectores de modelos distintos.

## Servicios externos
| Servicio | Cuándo | Qué sale de tu equipo |
|---|---|---|
| Claude (tu suscripción) | Al **indexar** (resumir y extraer conceptos) y cuando lees texto recuperado en la conversación | Fragmentos de tus documentos de memoria |
| `api.osv.dev` | Auditoría de vulnerabilidades, máx. cada 24 h | Solo nombre y versión de paquetes |
| Marketplace de Cognee (GitHub) | Instalar el plugin | Nada |
| Registros de imágenes y CDN de Cytoscape | Primera construcción | Nada |

## Dependencias de los proyectos que vigila
Lee lockfiles y manifiestos: `poetry.lock`, `package-lock.json`, `requirements*.txt` fijados con `==`, `packages.yml` de dbt, `Dockerfile` (versiones de Node/Python). La auditoría OSV cubre PyPI y npm; los paquetes de dbt Hub se inventarían pero OSV no los cubre.
