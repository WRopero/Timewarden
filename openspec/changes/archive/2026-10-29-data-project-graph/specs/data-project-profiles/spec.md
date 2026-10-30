## ADDED Requirements

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
