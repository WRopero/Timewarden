# project-type-detection Specification

## Purpose
Detect the project type (profile layers) at install time and ask the user when the evidence is ambiguous, without guessing.

## Requirements

### Requirement: Project type detection
The installer SHALL inspect the repository and propose a profile made up of one or two layers among `dbt`, `dataform`, `snowflake`, `bigquery`, `webapp`, `python-lib` and `generic` (e.g. `dbt,snowflake`, `dataform,bigquery`), with a confidence level between 0 and 1 and the list of evidence (files that motivated the decision).

#### Scenario: Clear dbt project
- **WHEN** the repository contains `dbt_project.yml`
- **THEN** the proposed layers are `dbt` and `snowflake` if the configured adapter is Snowflake (`dbt,bigquery` if it is BigQuery), and the confidence is at least 0.75

#### Scenario: Clear Dataform project
- **WHEN** the repository contains `workflow_settings.yaml` or `dataform.json` and `.sqlx` files under `definitions/`
- **THEN** the proposed layers are `dataform` and `bigquery` with confidence of at least 0.75

### Requirement: Mandatory question when ambiguous
When the confidence is below 0.75, there is evidence of two data profiles at once, or the repository is nearly empty, the detection MUST exit with a non-zero exit code reserved for "ambiguous" and the agent MUST ask the user before installing. The installer MUST NOT guess.

#### Scenario: dbt without a detectable adapter
- **WHEN** `dbt_project.yml` exists and there is no evidence of the adapter
- **THEN** the result is ambiguous and the user is asked which warehouse they use (Snowflake, BigQuery, or other)

#### Scenario: Empty repository
- **WHEN** the repository contains no recognizable files
- **THEN** the result is ambiguous and the user is offered a manual choice among the available profiles

### Requirement: Explicit choice
The installer SHALL accept the profile as an explicit argument and record it in the project contract so that hooks and skills can use it.

#### Scenario: Forced profile
- **WHEN** installing with `--profile dataform-bigquery`
- **THEN** the project contract records that profile and automatic detection is not run

### Requirement: Databricks detection
The detector SHALL recognize the `databricks` layer from `databricks.yml` bundles, the `dbt-databricks` adapter or `type: databricks` profiles, Delta Live Tables usage and `.databrickscfg` references, and MUST ask when Databricks and another warehouse both have evidence without a clear owner.

#### Scenario: Bundle repository
- **WHEN** the repository contains `databricks.yml`
- **THEN** the detected layers include `databricks` with the bundle as evidence
