# data-system-sync Specification

## Purpose
TBD - created by archiving change data-project-graph. Update Purpose after archive.

## Requirements

### Requirement: Tool-native exports as a source
The system SHALL prefer the data tool's own offline exports when available (`dataform compile --json`, dbt `target/manifest.json` produced by `dbt parse`) and MUST fall back to the built-in static parser when the CLI or its dependencies are missing, recording which source produced each node.

#### Scenario: Dataform compile available
- **WHEN** the Dataform CLI and project dependencies are installed
- **THEN** the graph is built from the compiled graph, including resolved target names, and nodes record `source: compile`

#### Scenario: CLI missing
- **WHEN** the CLI is not installed
- **THEN** the static parser is used, nodes record `source: static`, and the briefing says the graph is static-only

### Requirement: Opt-in live metadata sync
The system SHALL read metadata from the live data system only for environments whose catalog entry sets `metadata_sync: true`, using read-only metadata queries (tables, columns, partitioning, clustering, catalog lineage), MUST NOT read table data, MUST NOT execute write or production-run commands, and MUST use the user's existing authentication.

#### Scenario: Environment not opted in
- **WHEN** an environment lacks `metadata_sync: true`
- **THEN** no live query is issued for it

#### Scenario: Live and declared differ
- **WHEN** a table exists in the system but not in the repository, or the reverse
- **THEN** the graph records the node with `declared: false` or `live: false` and `check` reports the drift

### Requirement: Change-driven incremental update
The system SHALL compute a fingerprint per source and perform no regeneration and no indexing when every fingerprint is unchanged, and when something changed it SHALL regenerate documents deterministically and re-index in Cognee only documents whose content hash changed.

#### Scenario: Nothing changed
- **WHEN** a session starts and no fingerprint changed
- **THEN** no document is written, no Cognee call is made, and the briefing reports the graph as current

#### Scenario: One model changed
- **WHEN** one model file changes
- **THEN** only the documents containing that model or its relations change and only those are re-indexed

### Requirement: Session-start hook with budgets
The SessionStart step SHALL launch the sync detached and bounded by a time budget, a live-signature TTL and `max_auto_sync_docs`, SHALL NOT block the session, and SHALL skip indexing silently when the memory stack is unavailable, leaving the documents pending.

#### Scenario: Stack down
- **WHEN** the Cognee stack does not respond
- **THEN** documents are still regenerated locally, indexing is deferred, and the session starts normally

#### Scenario: Large change
- **WHEN** more documents changed than `max_auto_sync_docs`
- **THEN** only up to the limit are indexed automatically and the briefing tells the agent how to index the rest
