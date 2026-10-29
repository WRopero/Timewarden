# Continuity between sessions ("pick up as if you never closed")

Principle: what is **always** needed is injected once on opening (cheap and deterministic); anything deeper is queried from Cognee **only if needed**.

| Layer | What it provides | When | Cost |
|---|---|---|---|
| 1. `CLAUDE.md` | project rules, stack, phases | every session (native) | already included |
| 2. Briefing (`memory_brief.py`, SessionStart hook: startup/resume/clear/compact) | goal, current decisions, business rules, pending items, last handoff, obsolete notes (Git) | on opening and after compacting | ~1,000 tokens, 0 LLM calls, 0 Cognee queries |
| 3. Checkpoint (`memory_checkpoint.py`, SessionEnd + PreCompact hooks) | branch, uncommitted changes, latest commits and the user's latest requests | on closing/compacting | 0 tokens |
| 4. Semantic handoff (skill `project-memory-handoff`, requested by CLAUDE.md when closing a milestone) | decisions, why, tests, next action | when finishing a task | ~1 turn |
| 5. Durable memory (`project-memory-document` + `memctl.sh sync`) | decisions/implementations/rules that must survive for months | per milestone | ingestion (the expensive part) |
| 6. Cognee `recall` (CHUNKS, top_k 3) | deep history that doesn't fit in the briefing | on demand, 1×/task | 0 LLM + whatever is retrieved |

## A day's flow
You open Claude in the project → briefing loaded (it knows decisions, business rules, pending items and where you left off) → you work → when closing a milestone: handoff (+ document and sync if there was a decision) → you close; the hook leaves the checkpoint → tomorrow the briefing includes that handoff.

## Honest limits
- The briefing is **deterministic**: it summarizes what is written in `docs/agent-memory/`. If something wasn't documented or included in a handoff, it isn't remembered. The key discipline is the handoff/documenting when closing.
- The automatic checkpoint only knows about Git and your latest requests; it doesn't know *why* you decided something.
- Briefing cap is 6,000 characters: with many documents, prioritization is needed (today: only `verified|draft` decisions, rules, 10 pending items, 1 handoff, 6 obsolete).
- Tested: a new session without tools answered decisions, rules and pending items (1 turn, $0.0075). Not tested: several days of real use.
- The plugin's prompt preference/injection was turned off and the global `autoMemoryEnabled` was restored (the plugin had set it to `false`).
