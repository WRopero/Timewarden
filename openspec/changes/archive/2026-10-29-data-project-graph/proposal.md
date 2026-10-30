## Why

In data repositories (dbt, Dataform, Databricks, warehouse-only SQL) an agent keeps re-discovering the same facts: which models exist, how tables and models depend on each other, which conventions the project follows, and how to connect to each environment. Prose notes do not answer "what breaks if I change this model?" and they do not stop the agent from asking, session after session, how to connect. A deterministic, offline project graph plus a non-secret connection catalog removes both problems, and stays generic so the kit installs on any machine.

## What Changes

- Add `scripts/data_graph.py`: builds from the repository (static scan, plus the tool's own offline exports when the CLI is installed: `dataform compile --json`, `dbt parse` / `manifest.json`) and, optionally, from the live system's metadata. It produces a lineage graph (`graph.json`) of models, sources, seeds, snapshots, exposures, tests, jobs and pipelines, with `ref`/`source`/table-read edges.
- Generate Markdown documents from the graph under `docs/agent-memory/data-graph/` (overview, observed conventions, per-folder model cards, sources) so the existing Cognee sync indexes them and Cognee builds its own knowledge graph on top.
- Add query commands (`find`, `show`, `upstream`, `downstream`, `impact`, `path`, `check`) that answer lineage questions exactly and offline, so the agent consults them before asking or opening many files.
- Mine conventions from the graph (layer naming prefixes, materialization per layer, test and description coverage, layering violations) and keep human-written rules in a preserved `rules.md`.
- Add `scripts/data_connect.py` and `.agent-memory/connections.yaml`: a committed, secret-free catalog of how to connect per environment (system, auth method, env var NAMES, ready-to-run commands), pre-filled from the detected profile and project files, plus a `check` that reports which CLIs and env vars exist on the current machine without printing values.
- Add `scripts/data_sync.py`: an incremental, change-driven sync. Tier A (default, no credentials) uses repo files and offline tool exports; Tier B (opt-in per environment, read-only metadata only) reads real tables, columns, partitioning and catalog lineage from BigQuery/Dataform, Snowflake or Databricks. A cheap fingerprint decides whether anything changed; only then are documents regenerated and only the changed documents are re-indexed in Cognee.
- Add a SessionStart hook step that runs the sync in the background, bounded by a time and document budget, so the memory stays current without the agent or the user asking.
- Add a `databricks` profile layer and detection (bundles, `dbt-databricks`, DLT, three-part table names).
- Wire it in: installer builds graph and catalog for data layers, the SessionStart briefing surfaces graph freshness and the connection summary, new skill `project-memory-data-graph`, rules in the generated `CLAUDE.md` section ("query the graph and the catalog before asking").
- Bump the kit to 0.3.0 and add `tests/` with neutral fixtures.

## Capabilities

### New Capabilities
- `data-project-graph`: offline lineage graph of a data repository, generated memory documents, query and check commands, observed conventions.
- `data-system-sync`: change-driven incremental sync from tool exports and (opt-in) live system metadata into the graph and Cognee, triggered by a session-start hook.
- `data-connection-catalog`: secret-free per-environment connection catalog and machine capability check.

### Modified Capabilities
- `data-project-profiles`: adds the `databricks` layer and the rule that data profiles tell the agent to consult the graph and catalog before asking.
- `project-type-detection`: detects the `databricks` layer.

## Impact

- New files: `scripts/data_graph.py`, `scripts/data_connect.py`, `scripts/data_sync.py`, `profiles/databricks/*`, `skills/project-memory-data-graph/`, `tests/`.
- Changed files: `scripts/detect_project_type.py`, `scripts/install_project.py`, `scripts/memory_brief.py`, `scripts/memctl.sh`, `templates/*/CLAUDE.memory-section.md`, `docs/DATA_PROJECTS.md`, `dev/export_kit.sh`, `VERSION`.
- No new runtime dependencies (stdlib only; PyYAML is used when importable, with a built-in fallback parser).
- Security: live sync is opt-in per environment, read-only, metadata only (never table data), and uses the user's own existing authentication; the scanner never reads `profiles.yml` secrets, key files, `.env*` or sample data; the catalog stores env var names, never values.
