## Context

The kit already indexes `docs/agent-memory/**/*.md` into Cognee, which builds its own knowledge graph from text. That graph is good for semantic recall but unreliable for exact structural questions (every downstream dependency of a model). Data repositories encode that structure explicitly (`ref()`, `source()`, `${ref()}`, bundle resources), so it can be extracted deterministically.

## Decisions

1. **Two source tiers.** Tier A (default): repository files plus the tool's own offline exports when the CLI and project dependencies are present (`dataform compile --json`, `dbt parse` then `target/manifest.json`), falling back to the built-in static parser. Needs no warehouse access or credentials. Tier B (opt-in per environment in `connections.yaml`, `metadata_sync: true`): read-only metadata from the live system (BigQuery `INFORMATION_SCHEMA` and Dataform compilation results; Snowflake `INFORMATION_SCHEMA`; Databricks Unity Catalog and lineage system tables) using the user's existing authentication. Never table data, never writes, never production-run commands.
2. **Two layers of memory.** `graph.json` (exact, queried by CLI) and generated Markdown (semantic, indexed by Cognee). Both come from the same scan, so they cannot disagree.
3. **Generated files are marked and regenerated; human rules are preserved.** Generated documents carry `generated: true` in the frontmatter and are overwritten; `docs/agent-memory/data-graph/rules.md` is never overwritten.
4. **Chunk-friendly documents.** One card document per model folder, capped in size, to keep Cognee chunks coherent and indexing cost bounded.
5. **Parsers.** dbt: `.sql` Jinja `ref`/`source`/`config`, plus YAML properties (models, sources, seeds, snapshots, exposures, tests). Dataform: `.sqlx` config block and `${ref()}`, `declare`, JS `publish`/`ref`. Databricks: bundle `resources` (jobs, pipelines), notebook/SQL three-part table reads, DLT `@dlt.table`/`dlt.read`. YAML via PyYAML when importable, otherwise a small built-in subset parser.
6. **Connection catalog is declarative and secret-free.** `connections.yaml` holds per environment: system, auth method, env var names, project/dataset/schema/account identifiers, and command templates. `data_connect.py init` drafts it from the profile and project files and marks unknowns `TODO`; `check` reports tool and env var presence only.
7. **Change-driven sync.** `data_sync.py` computes a fingerprint per source: a hash of the relevant repository files (tier A) and a cheap live signature such as latest table modification time or object counts (tier B, rate-limited by a TTL). If the fingerprint is unchanged it exits without work. If changed it rebuilds, writes documents deterministically (byte-identical when content is unchanged) and re-indexes in Cognee only the documents whose hash changed. Indexing is detached, bounded (`max_auto_sync_docs`) and skipped silently if the stack is down, leaving the documents `pending` for the next run.
8. **Hook.** The SessionStart briefing step launches `data_sync.py run --if-changed` detached; the briefing reports the last result instead of waiting. Auto-index is controlled by `data_graph.auto_sync` in `project.yaml` (default true for tier A documents, never for tier B unless the environment opted in).
9. **Relation cards for Cognee.** Documents state relations as plain sentences (`mart_orders depends on stg_orders and stg_customers`) so Cognee's own graph extraction captures them; exactness for queries stays with `graph.json`.
10. **Neutrality.** No company, client or pilot names anywhere in code, docs, fixtures or tests; the export scan keeps enforcing it.

## Risks / Trade-offs

- Dynamic Jinja (`ref(var)`, macros that generate refs) cannot be resolved statically: such nodes are flagged `dynamic` and listed in `check` rather than guessed.
- Large projects (thousands of models): documents are split per folder and the scan is linear; a time budget guards the SessionStart hook.
- Convention mining is inferential: it is labeled "observed", never presented as a rule until a human promotes it to `rules.md`.

## Open Questions

None blocking; manifest.json ingestion and warehouse-side metadata (INFORMATION_SCHEMA) are deferred.
