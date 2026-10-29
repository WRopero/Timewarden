## Context

The system already works in a pilot project: Cognee in Docker, a deterministic briefing injected at `SessionStart`, a checkpoint at `SessionEnd/PreCompact`, `project-memory-*` skills, and a read-only dashboard. This change makes it distributable and specializes it.

## Goals / Non-Goals

**Goals:** real portability (a single `.zip`), data profiles, security/version memory with automatic auditing, per-branch deployments, indexed OpenSpec.
**Non-Goals:** supporting systems other than macOS + Docker Desktop; connecting to BigQuery or Snowflake; replacing `npm audit`/`pip-audit` in CI.

## Decisions

1. **Detection by weighted evidence, not by a single marker.** `detect_project_type.py` scores files (e.g. `dbt_project.yml`, `workflow_settings.yaml`, `.sqlx`, `*.tf` with `google_bigquery_*`) and returns `PROFILE`, `CONFIDENCE` and `EVIDENCE`; exit code 3 = ask (same contract as the language). Rejected alternative: always ask — it adds friction in obvious cases.
2. **Profiles as data (`profiles/<id>/`)**: `profile.yaml` (exclusions, extra sources, extra lockfiles), `rules.<lang>.md` (injected into `CLAUDE.md`) and templates. Adding a profile does not require touching code.
3. **OSV as the audit source**: a single API with no tools to install, covering PyPI and npm with the exact version from the lock. Only name+version leave the machine. Alternative: `pip-audit`/`npm audit` (they require installation and each covers one ecosystem); `npm audit` is kept as a manual cross-check.
4. **The startup hook launches the audit detached** (`start_new_session`), once every 24 h, so it does not block the session. The result lives outside the repository; only the pending-items document is versioned.
5. **Dependency registry covers direct dependencies only** + history; transitive ones are audited but not inventoried (avoids noise).
6. **Relocatable bundle**: root resolved from the script's location (`MEMORY_SYSTEM_HOME` to override) and written to `project.yaml` (`memory_system:`) so that skills and rules do not carry hard-coded paths. The dashboard is included as source code in the `.zip`.
7. **Packaging with allowlist + scanning**: `package_bundle.sh` copies only what is declared and fails if it finds forbidden terms or secret patterns.

## Risks / Trade-offs

- [Generic data rules may not fit the team's convention] → profiles are editable text in the project, and the agent must ask when in doubt.
- [OSV may list advisories that do not apply to actual usage] → exceptions file and manual verification; the briefing only prioritizes, it does not block.
- [The neutrality scan may produce false positives] → the list of terms is configurable in the script.
