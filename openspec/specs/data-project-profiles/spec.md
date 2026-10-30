# data-project-profiles Specification

## Purpose
Give data projects (dbt, Dataform, Snowflake, BigQuery) their own operating rules, credential exclusions, and deployment criteria.

## Requirements

### Requirement: Memory rules for data projects
Each data profile SHALL provide the agent with operating rules that are injected into the memory section of the project's `CLAUDE.md`, along with memory document templates specific to data work (models, sources, lineage, environments, costs).

#### Scenario: Dataform profile on BigQuery
- **WHEN** the project uses the `dataform` and `bigquery` layers
- **THEN** the rules include estimating bytes processed before running expensive queries (dry run), requiring partitioning and clustering on large tables, not running or rescheduling production workflows without approval, and distinguishing environments by project and dataset

#### Scenario: dbt profile on Snowflake
- **WHEN** the project uses the `dbt` and `snowflake` layers
- **THEN** the rules include respecting targets (`dev`/`prod`), not running `dbt run` or `dbt build` against `prod` without approval, declaring tests and documentation on every model, and watching warehouse cost (size and auto-suspend)

### Requirement: Credential security in data projects
Profiles MUST forbid storing credentials, service accounts, private keys, or the contents of `profiles.yml` in memory, and MUST exclude credential files and outputs containing real data from indexing.

#### Scenario: Excluded files
- **WHEN** a data profile is installed
- **THEN** the project contract excludes `profiles.yml`, service account `*.json` files, `.env*`, and sample data directories

### Requirement: Data tool versions as monitored dependencies
The dependency registry SHALL include the versions of dbt (`packages.yml` packages and adapters), `@dataform/core`, and the CLI when present, so that security-related changes are recorded.

#### Scenario: dbt version change
- **WHEN** the pinned version of a dbt adapter or package changes
- **THEN** the history records the date, previous version, and new version, and if the commit mentions a vulnerability it is marked as `security`

### Requirement: Deployment in data projects
For data projects, "deployed" SHALL be understood as the commit actually executed or published in the environment (Dataform release configuration or dbt production job), and is only recorded after its execution has been verified.

#### Scenario: Recording after a production run
- **WHEN** the production job finishes successfully for a commit
- **THEN** the agent records that commit under the `prod` environment in the deployment registry

### Requirement: Databricks layer
The system SHALL provide a `databricks` profile layer with operating rules (Unity Catalog three-part names, bundle targets, job and cluster cost awareness, no production deploy or run without approval) and credential exclusions (`.databrickscfg`, tokens, `.env*`).

#### Scenario: dbt on Databricks
- **WHEN** the project uses the `dbt` and `databricks` layers
- **THEN** the rules include respecting targets, not running against production without approval, and using SQL warehouses sized for the workload

### Requirement: Consult the graph and catalog first
Data profiles SHALL instruct the agent to query the project graph for structure and lineage and to read the connection catalog before asking the user how models relate or how to connect.

#### Scenario: Question about a model
- **WHEN** the agent needs the dependencies or consumers of a model
- **THEN** it queries the graph instead of searching the repository file by file
