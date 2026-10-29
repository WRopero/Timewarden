# Arquitectura (como quedo instalada)

```
Mac (host)                                   Docker Desktop (VM 8 GB)  red: agents_memory_net
 Claude Code + plugin cognee-memory 1.7.4 --> :45874 agents_cognee_api (cognee 1.6.5, gunicorn)
   hooks / skills / MCP  ------------------> :45873 agents_cognee_mcp  (--api-url -> agents_cognee_api:8000)
 observer (claude-observer.py, 127.0.0.1:8017)  <-- host.docker.internal:8017 (Bearer token) -- desde la API
 claude -p (haiku, suscripcion)                    agents_postgres (pgvector pg17, sin puerto publicado)
 OTel (claude-memory) -----------------> :45875 agents_otel_collector -> volumen agents_telemetry_raw
                                                   agents_analytics (perfil eval, DuckDB, job bajo demanda)
```
Volumenes: `agents_pgdata`, `agents_graph_data` (`/cognee-storage`: grafo Ladybug + datos crudos),
`agents_model_cache` (`/models`, fastembed), `agents_telemetry_raw`, `agents_analytics_data`.

## Flujo de escritura (verificado)
`sync_markdown.py` → por documento nuevo/cambiado: (borra `data_id` viejo) → `POST /api/v1/add` (idempotente por
contenido) → una vez por lote `POST /api/v1/cognify` (usa el observer) → busca el `document_id` en CHUNKS →
marca `indexed` en `~/.local/share/agents_memory_system/registry.json`.

## Aislamiento (verificado)
`ENABLE_BACKEND_ACCESS_CONTROL=true` + `VECTOR_DATASET_DATABASE_HANDLER=pgvector_shared` + `GRAPH_DATASET_DATABASE_HANDLER=ladybug`:
cada dataset obtiene su esquema `ds_<dataset_id>` en `agents_memory` y su archivo `<user_id>/<dataset_id>.lbug`.
`forget` de un dataset elimina ambos y no toca al otro.

## Lecciones de la instalacion (gotchas, en el orden en que aparecieron)
1. `pgvector_shared` **exige** `ENABLE_BACKEND_ACCESS_CONTROL=true`, lo que activa usuarios/auth (`REQUIRE_AUTHENTICATION=true`).
2. El email del usuario por defecto se valida: dominios reservados (`.local`) rompen el arranque. Usar un dominio real.
3. Volumenes nombrados nacen **root**: el usuario `cognee` no puede escribir en `/models` → capa `cognee.Dockerfile` que crea/chown el directorio.
4. Con access control hay que dar `VECTOR_DB_HOST/PORT/NAME/USERNAME/PASSWORD` aunque ya existan `DB_*`; si no, `/health` da 503 "Missing required pgvector credentials".
5. El MCP envia `Authorization: Bearer` por defecto; las API keys autoalojadas exigen `COGNEE_API_AUTH_SCHEME=x-api-key`.
6. El collector es distroless y corre como uid 10001: su volumen necesita un init (`agents_telemetry_init`) que haga chown.
7. El `recall` del MCP espera `datasets` como **string**; un nombre inexistente da 404 `Dataset(s) not found`.
8. Con `COGNEE_BASE_URL` en loopback el plugin se considera "local" y tiene `COGNEE_CODE_AUTOINDEX=auto` → fijar `off`.
9. `COGNEE_CAPTURE=false` aun registra sesiones (metadatos); no guarda contenido.
10. `host.docker.internal` **si** alcanza el observer que escucha solo en `127.0.0.1` (Docker Desktop for Mac); requiere el token.
11. Las metricas OTel delta subcuentan en sesiones cortas (ultima ventana no se vacia): los logs `api_request` son la fuente autoritativa.
12. En zsh una variable con un comando compuesto (`C="docker compose -f ..."; $C up`) no se separa en palabras: usar `scripts/dc.sh`.
