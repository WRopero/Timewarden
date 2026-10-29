---
name: project-memory-bootstrap
description: Use to onboard a new repository into project memory or to reconstruct its initial map. Installs the memory contract and hooks, drafts project.md and architecture.md from real documentation, and proposes a 10-20 document pilot corpus. Do not use for repositories that already have .agent-memory/project.yaml.
---

# project-memory-bootstrap

> `<MS>` = path to the memory system: the `memory_system` field of `.agent-memory/local.yaml` (local to each machine).

Onboards a repository into memory without scanning the disk or inventing content.

## Procedure
1. Confirm the scope with the user: a single repository, its `project_id` (stable, not the checkout path), and data that must not be included (clients, banking).
2. Install the contract: `python3 -I <MS>/scripts/install_project.py <repo> --project-id <id>` (idempotent; add `--no-capture` if session capture should stay off).
3. Read **real documentation**: README, `CLAUDE.md`, specs, runbooks, configuration. Prefer what is written over what is inferred from the code.
4. Draft `docs/agent-memory/project.md` (an *Objective* section of 1 to 3 sentences: the briefing cites it) and `architecture.md` with `status: draft`, citing real `source_paths` and `source_commit` = `git rev-parse --short HEAD`.
5. Propose the pilot corpus (10-20 documents): decisions, implementations, business rules, runbooks **that are not already in `CLAUDE.md`**. List the documentation gaps instead of filling them in.
6. If the user approves: create the documents with the templates from `.agent-memory/templates/`, then `memctl.sh sync <repo>` (plan) and, with their approval, `--apply`. Warn about the cost (~2 Claude calls per chunk).
7. Create 20 questions with an expected source in `<MS>/evals/cases.<id>.jsonl` and run `memctl.sh eval <repo>`.

## Output
Project registration, `project.md`, `architecture.md`, list of gaps, `eval` result.

## Limits
- Do not scan the disk, do not ingest dependencies or client datasets, do not claim to understand the entire repository.
- No credentials or real sensitive data in the documents.
- Unvalidated documents stay `draft`; `verified` only after running the check.
