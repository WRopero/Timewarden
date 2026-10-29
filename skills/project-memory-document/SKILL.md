---
name: project-memory-document
description: Use after a significant completed change, a confirmed decision, a validated solution, or when the user says "document/remember this" in a project with .agent-memory/project.yaml. Writes or updates Markdown under docs/agent-memory/ and queues synchronization to Cognee.
---

# project-memory-document

> `<MS>` = path to the memory system: the `memory_system` field of `.agent-memory/local.yaml` (local to each machine).

Stores verifiable knowledge as reviewable Markdown; Cognee only indexes it.

## Procedure
1. Decide the type: `implementations/` (change + evidence), `decisions/` (decision + alternatives), `runbooks/`, `business/` (definitions). Update an existing note if applicable instead of creating another one.
2. Use the frontmatter schema: `id, project_id, type, status, created_at, updated_at, source_commit (real hash: git rev-parse --short HEAD), source_paths, supersedes, tags`.
3. Write up: problem and scope, implementation, decision and reasoning, alternatives and failures, **validation evidence**, limitations, pending items.
4. Separate observations from hypotheses. A response from Claude is not evidence; an executed test is.
5. `status: verified` only if you executed the validation. Otherwise, `draft`. If it replaces something, fill in `supersedes` and mark the previous one `superseded`.
6. Sync **only once per task or milestone** (not after every edit; each new chunk costs ~2 calls to Claude): `<MS>/scripts/memctl.sh sync <repo> --apply`
   and report the actual status: saved locally / sent / indexed and retrievable.

## Limits
- Never store credentials, `.env`, tokens, personal data of third parties, or real banking data.
- Do not create a note for every response; only for significant changes.
- Do not run `forget` with `everything` or delete datasets.
