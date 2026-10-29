# Dependencies

## On your machine (what you need to have)
| Tool | Tested version | Purpose |
|---|---|---|
| macOS + Docker Desktop | Docker Engine 27.5.1, Compose 2.32.4, 8 GB VM and 8 CPUs | Runs the stack. **Only validated platform**; on Linux/Windows the installer warns and nothing is guaranteed |
| Claude Code | 2.1.311 (minimum 2.1.287) with an active login | Agent, hooks, skills and MCP; the observer uses your subscription |
| Python 3 | 3.12 | All scripts (standard library only) |
| git | any recent version | Branch state, freshness, deployments |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | 1.15.0 | Drives every change; part of the installation |
| Internet (first time) | — | Docker images, embeddings model (~640 MB), Cognee marketplace plugin |

## Images and components (pinned in `config/versions.lock`)
| Component | Version | Purpose |
|---|---|---|
| Cognee (API) | 1.6.5 | Ingestion, knowledge graph, search |
| Cognee MCP | `main-37f788b` | Exposes `recall` to Claude Code |
| PostgreSQL + pgvector | pg17 / pgvector 0.8.x | Vectors and metadata |
| OpenTelemetry Collector | 0.111.0 | Claude Code telemetry (tokens) |
| `cognee-memory` plugin | 1.7.4 | Cognee capture hooks and skills inside Claude Code |
| Embeddings | `jinaai/jina-embeddings-v2-base-es` (768 dim, fastembed 0.8.0) | Bilingual semantic search **locally**, with no internet or cost |
| DuckDB (analytics, optional) | 1.1.3 | Normalizes telemetry and usage on demand |
| Dashboard: FastAPI / uvicorn / psycopg / httpx | 0.115.6 / 0.32.1 / 3.2.3 / 0.27.2 | Read-only dashboard |
| `wollomatic/socket-proxy` | 1.11.0 | Read-only proxy to the Docker engine for the dashboard |
| Cytoscape.js | 3.30.2 | Draws the graph in the dashboard (downloaded when the image is built) |

Changing the embeddings model forces a full reindex: vectors from different models are never mixed.

## External services
| Service | When | What leaves your machine |
|---|---|---|
| Claude (your subscription) | When **indexing** (summarizing and extracting concepts) and when you read retrieved text in the conversation | Fragments of your memory documents |
| `api.osv.dev` | Vulnerability audit, at most every 24 h | Only package names and versions |
| Cognee marketplace (GitHub) | Installing the plugin | Nothing |
| Image registries and Cytoscape CDN | First build | Nothing |

## Dependencies of the projects it monitors
It reads lockfiles and manifests: `poetry.lock`, `package-lock.json`, `requirements*.txt` pinned with `==`, dbt's `packages.yml`, `Dockerfile` (Node/Python versions). The OSV audit covers PyPI and npm; dbt Hub packages are inventoried but OSV does not cover them.
