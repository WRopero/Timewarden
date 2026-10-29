# Data projects: BigQuery, Dataform, Snowflake and dbt

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
| `package.json` with a web framework, `manage.py`, Django/FastAPI/Flask | `webapp` |

Typical combinations: `dbt,snowflake` · `dbt,bigquery` · `dataform,bigquery` · `bigquery` · `snowflake`.

**Cases where it asks:** dbt without a detectable adapter; dbt with evidence of two warehouses; Dataform alongside evidence of Snowflake; a repository with no recognizable evidence; dbt and Dataform at the same time. You can force it: `seed.sh project <repo> <id> --profile dataform,bigquery`.

## What changes per layer
| Layer | Rules the agent must follow (written into the project's `CLAUDE.md`) | Excluded from memory |
|---|---|---|
| **dbt** | Always `ref()`/`source()`; `profiles.yml` stays outside the repo and is not read; **never `run/build/seed/snapshot` against `prod` without approval**; explore with `compile`, `ls`, `show`, `--empty`; CI with `state:modified+ --defer`; tests and `contract` on marts; incrementals with `unique_key`; `--full-refresh` on large tables requires approval | `profiles.yml`, `target/`, `dbt_packages/`, `logs/` |
| **dataform** | Always `ref()`/`resolve()`; `dataform compile` before running; `run --dry-run`; **do not run or reschedule production workflows without approval**; environments per project or `schemaSuffix`; assertions; incrementals with `uniqueKey` and `updatePartitionFilter` | credentials, `node_modules/`, service accounts |
| **bigquery** | **dry run and estimated bytes before new or heavy queries**; no `SELECT *`; partitioning + `require_partition_filter` and clustering; same *location*; minimal IAM and no JSON keys in the repo; Terraform: `plan` before `apply`, **`apply`/`destroy` only with approval** | service accounts, `*.tfstate`, `*.tfvars`, `.terraform/` |
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
