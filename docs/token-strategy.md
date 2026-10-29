# Token Strategy

Sources: Cognee (cost technical note, `cognee-performance` skill, search types docs) and our own measurement (2026-10-26).

## Where the cost goes
| Stage | Cost | Evidence |
|---|---|---|
| **Ingestion (`cognify`)** | Dominant. ~2 LLM calls per chunk (summary ~27 % + graph ~73 %) | Cognee: ~23–25× the corpus tokens. Measured here: ~307 000 tokens for ~4 100 of corpus (~75×; each `claude -p` drags ~23 k of cached prompt) |
| `CHUNKS` query | 0 LLM calls | search types docs |
| `GRAPH_COMPLETION` query (MCP default without `search_type`) | ≥1 call | ditto; COT/DECOMPOSITION/CONTEXT_EXTENSION: several |
| Per-prompt injection by the plugin | up to 9 000 characters (~2 300 tokens) per prompt | plugin README (`COGNEE_INJECT_MAX_CHARS`) |
| Verifying by reading code | read tokens per file | Own A/B: B cost 3× A because of this and because of recall |

`chunkSize` did **not** help with small documents (3 chunks with 2000 or 4000 tokens; 6–7 calls): cost follows the number of paragraphs/sections.

## Rules
1. **Cognee only where direct Markdown is not enough.** Corpus < ~30 k tokens: load/read it directly (CLAUDE.md, grep). Ingestion break-even with a ~4 k-token corpus: >100 queries. Cognee pays off with a large corpus, several projects/agents, or relationships between documents (Cognee itself reports a break-even of ~23–26 queries with a 16–200 k-token corpus).
2. **Don't duplicate what is already in context.** CLAUDE.md is loaded in every session; indexing copies of it pays for ingestion with no benefit. Index what is *not* there (decision history, runbooks, specs).
3. **Ingest little and in batches:** `memctl.sh sync` once per task/milestone, never per edit. The hash registry already avoids reprocessing (0.28 s, 0 calls). Dense, concise documents: fewer paragraphs = fewer chunks.
4. **Query on demand:** explicit recall (skill) with `search_type=CHUNKS`, `top_k` 3–5, once per task. No automatic recall per prompt: capture is off and the sessions dataset is empty (the hook injects ~nothing); if it is ever enabled, `COGNEE_INJECT_MAX_CHARS=3000`, `COGNEE_RECALL_PASSAGE_CHARS=600`.
5. **Freshness via Git, not by reading:** `scripts/memory_stale.py` (0 tokens) decides whether code needs to be opened.
6. **Extras turned off (applied):** `AUTO_FEEDBACK=false`, `IMPROVE_AUTO_ENABLED=false` (server), `COGNEE_AUTO_IMPROVE_EVERY=0` (plugin), session capture off, `CODE_AUTOINDEX=off`.
7. **Measure before expanding:** `analytics` (A/B) + `memctl.sh eval`. A negative saving is a valid result.

## Levers that exist but were not applied (and why)
- `extractor="gliner"` (local graph without an LLM): only in the SDK `remember()`, not in the REST API of 1.6.5.
- Cheap models per stage (`LLM_EXTRACTION_MODEL`...): the observer already uses `haiku`, the cheapest available.
- `data_per_batch`/`chunks_per_batch`: spread the load, don't reduce tokens.
- Cognee's own prompt caching: not documented by them.
