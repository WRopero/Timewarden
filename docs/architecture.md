# Architecture (as installed)

```
Mac (host)                                   Docker Desktop (8 GB VM)  network: agents_memory_net
 Claude Code + cognee-memory 1.7.4 plugin --> :45874 agents_cognee_api (cognee 1.6.5, gunicorn)
   hooks / skills / MCP  ------------------> :45873 agents_cognee_mcp  (--api-url -> agents_cognee_api:8000)
 observer (claude-observer.py, 127.0.0.1:8017)  <-- host.docker.internal:8017 (Bearer token) -- from the API
 claude -p (haiku, subscription)                   agents_postgres (pgvector pg17, no published port)
 OTel (claude-memory) -----------------> :45875 agents_otel_collector -> volume agents_telemetry_raw
                                                   agents_analytics (eval profile, DuckDB, on-demand job)
```
Volumes: `agents_pgdata`, `agents_graph_data` (`/cognee-storage`: Ladybug graph + raw data),
`agents_model_cache` (`/models`, fastembed), `agents_telemetry_raw`, `agents_analytics_data`.

## Write flow (verified)
`sync_markdown.py` → for each new/changed document: (deletes the old `data_id`) → `POST /api/v1/add` (idempotent by
content) → once per batch `POST /api/v1/cognify` (uses the observer) → looks up the `document_id` in CHUNKS →
marks it `indexed` in `~/.local/share/agents_memory_system/registry.json`.

## Isolation (verified)
`ENABLE_BACKEND_ACCESS_CONTROL=true` + `VECTOR_DATASET_DATABASE_HANDLER=pgvector_shared` + `GRAPH_DATASET_DATABASE_HANDLER=ladybug`:
each dataset gets its own schema `ds_<dataset_id>` in `agents_memory` and its own file `<user_id>/<dataset_id>.lbug`.
`forget` on a dataset removes both and leaves the other untouched.

## Installation lessons (gotchas, in the order they appeared)
1. `pgvector_shared` **requires** `ENABLE_BACKEND_ACCESS_CONTROL=true`, which turns on users/auth (`REQUIRE_AUTHENTICATION=true`).
2. The default user's email is validated: reserved domains (`.local`) break startup. Use a real domain.
3. Named volumes are created as **root**: the `cognee` user cannot write to `/models` → `cognee.Dockerfile` layer that creates/chowns the directory.
4. With access control you must provide `VECTOR_DB_HOST/PORT/NAME/USERNAME/PASSWORD` even if `DB_*` already exist; otherwise `/health` returns 503 "Missing required pgvector credentials".
5. The MCP sends `Authorization: Bearer` by default; self-hosted API keys require `COGNEE_API_AUTH_SCHEME=x-api-key`.
6. The collector is distroless and runs as uid 10001: its volume needs an init (`agents_telemetry_init`) that does the chown.
7. The MCP `recall` expects `datasets` as a **string**; a nonexistent name returns 404 `Dataset(s) not found`.
8. With `COGNEE_BASE_URL` on loopback the plugin considers itself "local" and gets `COGNEE_CODE_AUTOINDEX=auto` → set it to `off`.
9. `COGNEE_CAPTURE=false` still records sessions (metadata); it does not store content.
10. `host.docker.internal` **does** reach the observer that listens only on `127.0.0.1` (Docker Desktop for Mac); it requires the token.
11. Delta OTel metrics undercount in short sessions (the last window is not flushed): the `api_request` logs are the authoritative source.
12. In zsh a variable holding a compound command (`C="docker compose -f ..."; $C up`) is not word-split: use `scripts/dc.sh`.
