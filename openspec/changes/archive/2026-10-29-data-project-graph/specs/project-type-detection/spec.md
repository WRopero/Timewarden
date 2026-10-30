## ADDED Requirements

### Requirement: Databricks detection
The detector SHALL recognize the `databricks` layer from `databricks.yml` bundles, the `dbt-databricks` adapter or `type: databricks` profiles, Delta Live Tables usage and `.databrickscfg` references, and MUST ask when Databricks and another warehouse both have evidence without a clear owner.

#### Scenario: Bundle repository
- **WHEN** the repository contains `databricks.yml`
- **THEN** the detected layers include `databricks` with the bundle as evidence
