## Why

The installation bundle for the project memory (Cognee in Docker + hooks + skills) was born in a specific web project and carries over its name, absolute paths, and assumptions (Django/Next.js). It is meant to be shared with teammates who also work on **data projects** (BigQuery + Dataform, Snowflake + dbt), where what matters to remember is different: lineage, partitioning, query cost, environments, permissions, and package/adapter versions. There is also no memory for **security and versions** (what is installed, when and why it changed), for **per-branch deployments**, or for the **OpenSpec specs**.

## What Changes

- The bundle detects the project type, **asks when it is ambiguous**, and applies a profile (dbt/Snowflake, Dataform/BigQuery, SQL/BigQuery with Terraform, web application, generic).
- Data profiles with the rules the agent must follow (BigQuery cost, partitions, environments, grants, dbt/Dataform tests, secrets kept out of the repo).
- Deterministic registry of dependencies and versions with history (reason `security` vs `upgrade`) and vulnerability auditing (OSV) launched automatically by the startup hook, with pending items visible in the briefing.
- Deployment registry per environment and per-branch status (already implemented; now formalized).
- OpenSpec specs and changes are indexed in the memory, and the briefing lists the active changes.
- Rule: when something is ambiguous, consult the memory before deciding or asking.
- **BREAKING**: the bundle no longer depends on paths, project names, or personal accounts; it is distributed as a self-contained `.zip` (includes the Management Memory panel) with a relocatable installation.

## Capabilities

### New Capabilities
- `project-type-detection`: detect project type, confidence, and a mandatory question if ambiguous.
- `data-project-profiles`: memory rules and templates for data projects (dbt/Snowflake, Dataform/BigQuery).
- `dependency-security-memory`: installed versions, change history, and automatic vulnerability auditing.
- `deployment-ledger`: which commit is deployed per environment and the status of each branch.
- `openspec-memory`: OpenSpec specs and changes as part of the memory.
- `ambiguity-recall-rule`: consult the memory when the task is ambiguous.
- `portable-bundle`: neutral, relocatable, verifiable `.zip` package.

### Modified Capabilities
<!-- First spec in the repository: there are no previous capabilities in openspec/specs -->

## Impact

- Code: `scripts/` (new `detect_project_type.py`, `memory_deps.py`, `memory_audit.py`, `memory_deploy.py`, `package_bundle.sh`), `seed-bundle/`, `skills/`, `templates/`, `profiles/`.
- Already installed projects: the contract (`.agent-memory/project.yaml`) gains optional fields; everything keeps working without them.
- Network: the audit queries `api.osv.dev` (only package names and versions); if there is no network it fails silently.
- Out of scope: Windows/Linux support (only macOS + Docker Desktop was tested), running `dbt`/`dataform` or connecting to BigQuery/Snowflake from the memory.
