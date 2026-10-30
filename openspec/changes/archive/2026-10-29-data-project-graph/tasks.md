## 1. Profile and detection
- [x] 1.1 Add `profiles/databricks/` (profile.yaml, rules.en.md, rules.es.md)
- [x] 1.2 Extend `detect_project_type.py` with the databricks layer and ambiguity rules
- [x] 1.3 Update installer layer handling

## 2. Graph engine
- [x] 2.1 `data_graph.py` scanners for dbt, Dataform and Databricks
- [x] 2.2 Markdown generation, conventions and size-capped cards
- [x] 2.3 Query commands and `check`
- [x] 2.4 Freshness hash and `--if-stale`

## 2b. Change-driven sync
- [x] 2b.1 Tier A: `dataform compile --json` and dbt `manifest.json` adapters with static fallback
- [x] 2b.2 Tier B adapters (BigQuery/Dataform, Snowflake, Databricks), opt-in, read-only, metadata only
- [x] 2b.3 Fingerprints, TTL, deterministic output, changed-only Cognee indexing with budget
- [x] 2b.4 SessionStart hook step (detached) and briefing status line

## 3. Connection catalog
- [x] 3.1 `data_connect.py init|show|check` with per-system templates
- [x] 3.2 Generated `connections.md` and secret redaction

## 4. Integration
- [x] 4.1 Installer builds graph and catalog for data layers
- [x] 4.2 Briefing section (freshness, environments, missing tools)
- [x] 4.3 Skill `project-memory-data-graph`, recall skill update, CLAUDE.md section rules (en/es)
- [x] 4.4 `memctl.sh graph|connect`

## 5. Quality and release
- [x] 5.1 Neutral fixtures and unit tests
- [x] 5.2 Validate on real local repositories (read-only)
- [x] 5.3 Docs, VERSION 0.3.0, export with neutrality scan, zip, publish
