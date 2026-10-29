---
name: project-memory-evaluate
description: Use after a pilot, a model/version change, or when memory quality or cost is in doubt in a project with .agent-memory/project.yaml. Measures retrieval quality, freshness, isolation, continuity and token consumption, and compares memory against reading the Markdown directly.
---

# project-memory-evaluate

> `<MS>` = path to the memory system: the `memory_system` field of `.agent-memory/local.yaml` (local to each machine).

Measures whether memory helps and how much it costs; a negative saving is a valid result.

## Procedure
1. **Retrieval:** `<MS>/scripts/memctl.sh eval <repo>` (20 ES/EN questions with expected `doc_id`; target >= 17/20 in top 5, p95 < 3 s). Unanswerable questions are only reported: abstaining is the agent's decision.
2. **Freshness:** `memory_stale.py <repo>`; count `STALE` and `NO-SOURCE` notes.
3. **Isolation (after version or dataset changes):** two test datasets with a different fact each; cross-query in both directions; `forget` one and check that the other remains intact.
4. **Continuity:** new session without tools and with `--settings '{"autoMemoryEnabled":false}'`; ask about decisions, rules and pending items; compare with the known truth.
5. **Consumption:** `python3 -I <MS>/scripts/weekly_report.py` (observer and sessions) and, for A/B, launch the variants with `scripts/claude-memory <id> A|B -- ...` and run `scripts/dc.sh --profile eval run --rm agents_analytics report --project <id>`.
   - A = read the same Markdown without plugin or MCP; B = with memory. Same commit, model and question; several repetitions; separate ingestion (once) from query.
6. Report **real** results with their limits (sample size, what was not measured) and recommend: continue, adjust or reduce.

## Limits
- Another LLM's answer is not the only reference truth; check against sources.
- Counting documents does not prove savings; a failed task with fewer tokens is not savings.
- History tests must disable Claude's native memory or they measure something else.
