---
name: project-memory-handoff
description: Use when switching session or agent, pausing a task, or before context compaction in a project with .agent-memory/project.yaml. Preserves observable task state (objective, constraints, files, tests, decisions, next action) so work can resume.
---

# project-memory-handoff

> `<MS>` = path to the memory system: the `memory_system` field of `.agent-memory/local.yaml` (local to each machine).

Preserves the observable state of a task. It does not store the model's internal reasoning.

## Procedure
1. Capture: objective, branch and commit (`git branch --show-current`, `git rev-parse --short HEAD`), constraints, files touched, uncommitted changes, tests and results, new decisions with their source, failed attempts, pending work and **next action**.
2. Explicitly mark anything not validated.
3. Write one file per task: `docs/agent-memory/handoffs/<date>-<task>.md` (shareable) or, if private, `docs/agent-memory/handoffs/_local/` (it is excluded from the index). Never a single global file.
4. **Deployment:** if something was deployed during the session, check its health and record it with `python3 -I <MS>/scripts/memory_deploy.py record <repo> <environment> --commit <sha> --note "..."`; the briefing compares by branch what is deployed and what is not. If nothing was deployed, do not record anything and say so in the handoff (branch, commit, "not deployed").
5. When resuming: validate the branch/commit against the real state before trusting the handoff; cross-check it against the repo.

## Compaction
`PreCompact` only persists state that is already available; it cannot invoke this skill. Keep the handoff up to date **during** the work and before approaching the context limit.

## Limits
- A checkpoint is not a validated conclusion. No secrets.
