---
name: project-memory-recall
description: Use when starting a task, resuming work, a requirement or design decision is ambiguous (query BEFORE deciding or asking), asking "why did we decide X", or investigating a known issue in a project that has .agent-memory/project.yaml. Retrieves project background from Cognee scoped to that project's dataset, then verifies it against the current repository.
---

# project-memory-recall

> `<MS>` = path to the memory system: the `memory_system` field of `.agent-memory/local.yaml` (local to each machine).

Retrieves project context from memory (Cognee) and checks it against the current code.

## Procedure
1. Read the repo's `.agent-memory/project.yaml`: use `memory_dataset` (never any other dataset) and `max_recall_results`.
2. If a recent local handoff exists (`docs/agent-memory/handoffs/` or the local checkpoint), read it first.
3. Search with the MCP tool `recall` (server `agents_cognee`):
   `query=<specific question>`, `datasets="<memory_dataset>"` (**string, not a list**), `search_type="CHUNKS"`, `top_k=5`.
   A `404 Not Found` almost always means a nonexistent dataset name: copy `memory_dataset` literally from `project.yaml`
   (e.g. `my-project-knowledge`, not `my-project`). Omitting `search_type` returns a graph-synthesized answer (uses more LLM).
   Each chunk begins with `[memoria-proyecto] ... doc_id=... status=... path=...`: use `path` as the source.
4. Discard or label anything with `status: superseded|archived` and be wary of `draft`.
5. **Check freshness without spending tokens:** `python3 -I <MS>/scripts/memory_stale.py <repo> <doc path>`.
   - `FRESH` (the `source_paths` have not changed since `source_commit`): use the memory as is, **do not open code**.
   - `STALE`: open only the listed files and report the difference; the memory is not an authority.
   - `NO-SOURCE`: treat it as `draft`; verify only if the decision is critical.
6. Answer briefly: decisions, constraints, sources (paths), uncertainties, and freshness.

## Limits
- Querying is cheap (CHUNKS does not use an LLM): do it when the briefing is not enough and before asking the user or assuming. Do not repeat the same question or query what the briefing already says; `top_k=3` unless evidence is missing.
- Do not query datasets from other projects/clients or inject whole documents (maximum ~1,500 tokens).
- Do not use `forget` or `remember` from this skill (read-only).
- If there is no evidence, say so and continue with direct inspection; do not make things up.
- If Cognee does not respond, read `docs/agent-memory/` directly (the Markdown is the canonical source).
