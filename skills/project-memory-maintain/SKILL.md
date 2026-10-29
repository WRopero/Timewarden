---
name: project-memory-maintain
description: Use when a decision was corrected, the architecture changed, or when auditing stale memory in a project with .agent-memory/project.yaml. Detects obsolete, duplicate or contradictory notes, marks supersession, and re-syncs the index incrementally.
---

# project-memory-maintain

> `<MS>` = path to the memory system: the `memory_system` field of `.agent-memory/local.yaml` (local to each machine).

Keeps memory truthful: it replaces, it does not accumulate contradictory versions.

## Procedure
1. **Audit without tokens:** `python3 -I <MS>/scripts/memory_stale.py <repo>` lists `STALE` (the `source_paths` changed since `source_commit`) and `NO-SOURCE`.
2. For each `STALE`: open only the listed files, compare them with the note, and decide: update (new `source_commit`, `updated_at`), replace (new note with `supersedes: [previous-id]` and the previous one becomes `status: superseded`) or archive (`archived`).
3. Look for duplicates and contradictions between notes (same topic, different rule). **Do not resolve by counting mentions**: check against the code/Git or ask the business owner. If there is no evidence, leave both marked and record the open question in a handoff.
4. Decision changes: create the new decision, do not edit the history of the previous one.
5. Sync **once** when finished: `memctl.sh sync <repo>` (plan) and `--apply`. Verify that the new version is retrieved and the old one is not (`memctl.sh eval <repo>` or a targeted `recall`).
6. Report: documents changed, sync status (indexed/unverified/error), pending obsolete notes.

## Limits
- Do not delete an entire dataset to fix a single note; `sync` already replaces by `data_id`.
- Before broad destructive operations, show the scope and ask for confirmation. Never `forget` with `everything`.
- Do not mark `verified` without validation evidence.
