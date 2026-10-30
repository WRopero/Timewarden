# Data projects: BigQuery, Dataform, Databricks, Snowflake and dbt

Timewarden works the same in any repository, but in data projects what matters to remember and monitor is different: **cost of each query, environments, lineage, quality, permissions, and tool versions**. That is what the *layered profiles* are for.

## How it decides what type of project it is
`scripts/detect_project_type.py` scores evidence in the repo and returns layers, confidence, and evidence. **If it's not clear, the installer exits with code 3 and the agent asks you**; it never guesses.

| Evidence | Layer |
|---|---|
| `dbt_project.yml` (+ `packages.yml`, `models/`) | `dbt` |
| `dbt-snowflake` in requirements / `type: snowflake` in a profile | `snowflake` |
| `dbt-bigquery` / `type: bigquery` | `bigquery` |
| `workflow_settings.yaml` or `dataform.json`, `.sqlx` files, `@dataform/core` | `dataform` (+ `bigquery`, because Dataform runs on BigQuery) |
| Terraform `google_bigquery_*`, `google-cloud-bigquery` client, `.sql` with `` `project.dataset.table` `` | `bigquery` |
| Snowflake connector/SDK | `snowflake` |
| `databricks.yml` bundle, `dbt-databricks`, `type: databricks`, Delta Live Tables (`import dlt`) | `databricks` |
| `package.json` with a web framework, `manage.py`, Django/FastAPI/Flask | `webapp` |

Typical combinations: `dbt,snowflake` · `dbt,bigquery` · `dbt,databricks` · `dataform,bigquery` · `databricks` · `bigquery` · `snowflake`.

**Cases where it asks:** dbt without a detectable adapter; dbt with evidence of two warehouses; Dataform alongside evidence of Snowflake; a repository with no recognizable evidence; dbt and Dataform at the same time. You can force it: `seed.sh project <repo> <id> --profile dataform,bigquery`.

## What changes per layer
| Layer | Rules the agent must follow (written into the project's `CLAUDE.md`) | Excluded from memory |
|---|---|---|
| **dbt** | Always `ref()`/`source()`; `profiles.yml` stays outside the repo and is not read; **never `run/build/seed/snapshot` against `prod` without approval**; explore with `compile`, `ls`, `show`, `--empty`; CI with `state:modified+ --defer`; tests and `contract` on marts; incrementals with `unique_key`; `--full-refresh` on large tables requires approval | `profiles.yml`, `target/`, `dbt_packages/`, `logs/` |
| **dataform** | Always `ref()`/`resolve()`; `dataform compile` before running; `run --dry-run`; **do not run or reschedule production workflows without approval**; environments per project or `schemaSuffix`; assertions; incrementals with `uniqueKey` and `updatePartitionFilter` | credentials, `node_modules/`, service accounts |
| **bigquery** | **dry run and estimated bytes before new or heavy queries**; no `SELECT *`; partitioning + `require_partition_filter` and clustering; same *location*; minimal IAM and no JSON keys in the repo; Terraform: `plan` before `apply`, **`apply`/`destroy` only with approval** | service accounts, `*.tfstate`, `*.tfvars`, `.terraform/` |
| **databricks** | Three-part Unity Catalog names; the bundle **target** decides the environment (`bundle deploy -t prod` and production jobs need approval); job clusters / serverless SQL warehouses with auto-termination; Delta partitioning/clustering on purpose, `OPTIMIZE`/`VACUUM` only via the pipeline; OAuth over tokens, secrets in secret scopes | `.databrickscfg`, `.databricks/` |
| **snowflake** | Cost = credits: warehouse size per workload, `AUTO_SUSPEND`, `QUERY_TAG`; key-pair or OAuth authentication; least-privilege roles; `CLONE` from production for development; `copy_grants` when recreating; production DDL only through the pipeline | `*.p8`, `*.pem`, `connections.toml` |

The full text of each layer is in [`profiles/<layer>/rules.es.md`](../profiles/) (and `.en.md`). **These are editable baseline rules**: if your team has a different convention, edit the "Project profile" section of `CLAUDE.md` and the agent will follow it.

## What the memory should remember in a data project
Recommended documents in `docs/agent-memory/` (the `project-memory-bootstrap` skill proposes them by reading the repo):
- **Model/table catalog:** grain, partitioning and clustering, owner, SLA, consumers. This is what avoids asking "is this table refreshed daily?".
- **Sources and contracts:** where each source comes from, its frequency, and its known quality.
- **Environments:** logical names of projects/datasets/accounts per environment (never credentials), `location`, and roles.
- **Costs:** bytes processed or credits per typical run (baseline) and a threshold-based approval rule.
- **Decisions:** why a table is incremental, why a backfill was done in windows, why a partitioning strategy was chosen.
- **Runbooks:** safe backfill, reprocessing a day, rolling back a release, key rotation.
- **Incidents:** what broke, cause, and fix (avoids repeating it).

## Deployment in data projects
"Deployed" is **not** "merged". It is the commit that the environment actually executed or published:
- **Dataform:** the *release config* compiled that commit and the production *workflow config* finished successfully.
- **dbt:** the production job (dbt Cloud, Airflow, CI/CD) finished successfully on that commit.
- **Terraform/BigQuery:** successful `apply` of that commit.

It is recorded only after verifying it: `python3 -I <KIT>/scripts/memory_deploy.py record . prod --commit <sha> --note "job #123 OK"`. The briefing will then tell you how many commits are still pending execution in `prod` and whether your branch is integrated and deployed.

## Versions and security in data
The following are monitored: `dbt-core`, the adapter (`dbt-snowflake`/`dbt-bigquery`), the packages in `packages.yml`, `@dataform/core` and the Dataform CLI, and the repo's Python/Node dependencies. The OSV audit covers PyPI and npm; dbt Hub packages **are inventoried but OSV does not cover them**: review them by hand when they change. When you bump a version for security reasons, cite the CVE/GHSA in the commit message and it will be recorded in the history as `security`.

## OpenSpec in data
An OpenSpec change in a data project should include verifiable scenarios in its specs: "**WHEN** a duplicate row arrives **THEN** the model keeps the most recent one per `id`", grain, freshness tolerance, and the tests/assertions that check it. `design.md` is the place for estimated cost (bytes/credits), incremental strategy, and backfill plan. The memory indexes those specs: the next session knows *why* the model behaves that way.

## What it does NOT do
It does not run `dbt`, `dataform`, `bq`, or `snowsql` by itself, does not connect to your warehouse, and does not read real data. The rules guide the agent; credentials and execution remain yours.

## Project graph: structure the agent can query instead of guessing
Prose notes cannot answer "what breaks if I change this model?". For `dbt`, `dataform` and `databricks` projects Timewarden builds a **lineage graph** from the repository and keeps it next to the memory.

**Sources, in order of fidelity** (recorded per system as `tier`): (1) the tool's own offline export when available: dbt `target/manifest.json` (reused if it is newer than the sources), Dataform `dataform compile --json` (run only if the CLI and `node_modules` exist, 90 s limit); (2) the built-in static parser (`ref()`/`source()`/config/YAML properties for dbt; `config {}` + `ref()`/`resolve()` + JS `publish` for Dataform; bundle jobs/pipelines, SQL and PySpark table reads/writes, DLT for Databricks). No warehouse access or credentials are needed for either.

| Command (`python3 -I <MS>/scripts/data_graph.py ...`, or `memctl.sh graph <repo> ...`) | Answers |
|---|---|
| `build [--tools auto\|off]` | Scans and writes `docs/agent-memory/data-graph/` |
| `find` / `show <node>` | Where an object is; its kind, path, columns, tests, direct dependencies and consumers |
| `upstream` / `downstream <node> [--depth N]` | Everything it reads / everything that reads it |
| `impact <node>` | What breaks if it changes, grouped by depth, with affected exposures |
| `path <a> <b>` | Shortest dependency path |
| `check` | Cycles, unresolved or dynamic refs, layer skips, orphans, test and description coverage, drift against the live system |

**What gets written for Cognee:** an `overview.md` (counts, **observed** conventions per folder: name prefix, materialization, test and description coverage, depth), one card document per folder (split at ~11k characters) stating relations as plain sentences (`fct_orders depends on: stg_customers, stg_orders.`) so Cognee's own graph extraction captures them, and `graph.json` for exact queries. Documents are generated deterministically (no timestamps or commit ids), so an unchanged model produces a byte-identical card and is not re-indexed. `data-graph/rules.md` is yours and is never overwritten: promote an observed convention to a rule only after confirming it.

**Limits:** refs built dynamically (`ref(var)`) cannot be resolved statically; those nodes are flagged `dynamic` and listed by `check` instead of guessed. Convention mining is inferential.

## Connection catalog: stop asking how to connect
`data_connect.py init` drafts `.agent-memory/connections.yaml` from the profile and non-secret project files (for dbt it reads the `profiles.yml` targets but keeps only non-secret keys such as type, account, role, database, warehouse, schema, project, dataset, location; secret-looking settings are recorded by **name only**, and `env_var('X')` references become variable names). Per environment it stores system, role (development/production), auth method, env var **names**, identifiers and command templates (validate, explore, dry-run, forbidden-without-approval) for BigQuery, Snowflake, Databricks, dbt and Dataform. `TODO` marks what could not be detected. `render` writes `docs/agent-memory/connections.md` (indexed), and `check` reports which CLIs are installed and which variables are set on **this** machine (never values, no network). The briefing lists the environments and any missing tool.

## Change-driven sync: current without being asked
`data_sync.py hook` runs inside the session-start briefing and costs ~0.15 s when nothing changed:

1. **Tier A fingerprint:** content hash of the repo files that can change the graph. Unchanged → nothing is rebuilt.
2. **Tier B live metadata (opt-in):** only environments with `metadata_sync: true` in the catalog, at most once per `live_ttl_hours`, and a full fetch only when a cheap signature moved (BigQuery `__TABLES__` count + latest modification; Snowflake `INFORMATION_SCHEMA.TABLES`; Databricks `tables list`). It reads table/column/partitioning metadata, **never table data**, runs only `SELECT`/list calls (a guard rejects anything else) with your own CLI authentication, and records drift (declared-but-missing, live-but-undeclared). Dataform workflow runs and lineage-system tables are not read in 0.3.0.
3. **Rebuild** only if something changed, then **index only the documents whose content hash changed**, detached, capped by `max_auto_sync_docs`, skipped silently if the memory stack is down (the briefing then says it is pending).

**Cost guard:** the first indexing of the graph documents is deliberately manual (`memctl.sh sync <repo> --apply`, every chunk costs Claude calls); only after that baseline exists do changes sync automatically. Settings in `.agent-memory/project.yaml`:

```yaml
data_graph:
  auto_sync: true          # re-index changed graph documents automatically (after the baseline)
  tool_exports: auto       # auto | off (static only)
  live_ttl_hours: 6
  max_auto_sync_docs: 20
```

**Validation status:** the parsers were exercised against real dbt and Dataform repositories; the live adapters are covered by tests with stubbed CLIs and have not been run against real BigQuery, Snowflake or Databricks accounts yet. Treat the first live sync of each system as something to watch.
