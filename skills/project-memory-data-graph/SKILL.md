---
name: project-memory-data-graph
description: Use in dbt, Dataform or Databricks projects whenever you need to know how models/tables relate, what a change would break, what a model reads or who consumes it, the project's conventions, or how to connect to an environment (BigQuery, Snowflake, Databricks). Query the offline lineage graph and the connection catalog BEFORE asking the user or reading files one by one.
---

# project-memory-data-graph

> `<MS>` = the `memory_system` field of `.agent-memory/local.yaml` (local to each machine). Run from the repo root.

## Structure and lineage (exact, offline, no tokens)
| Question | Command |
|---|---|
| What is this object / where is it | `python3 -I <MS>/scripts/data_graph.py find <text>` then `show <node>` |
| What does it read (all the way up) | `... upstream <node> [--depth N]` |
| Who uses it | `... downstream <node> [--depth N]` |
| What breaks if I change it | `... impact <node>` (grouped by depth, lists affected exposures) |
| How are A and B related | `... path <A> <B>` |
| Is the project healthy | `... check` (cycles, unresolved/dynamic refs, layer skips, orphans, test/doc coverage, live drift) |

Before editing a model, run `impact` and mention the downstream objects and exposures in your plan. Nodes marked `dynamic` have incomplete lineage: read the file.

## Meaning and history (semantic)
The generated cards in `docs/agent-memory/data-graph/` are indexed in memory: use `project-memory-recall` for "why", business meaning and decisions. Conventions listed in `overview.md` are **observed**, not rules; rules live in `data-graph/rules.md`.

## Connecting
Read `docs/agent-memory/connections.md` before asking how to connect. Run `python3 -I <MS>/scripts/data_connect.py check` to see which CLIs and env vars exist on this machine (names only). If a recipe is `TODO`, verify it and update `.agent-memory/connections.yaml`; never write a secret value.

## Freshness
The briefing says whether the graph is current. The session-start hook refreshes it when files changed. Force with `python3 -I <MS>/scripts/data_sync.py run --force`. Live metadata (tables, columns, partitioning) is mirrored only for environments with `metadata_sync: true`, read-only.

## Limits
Read-only skill. Do not run warehouse queries to answer lineage questions that the graph answers. Never put credentials in memory.
