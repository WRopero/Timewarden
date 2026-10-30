## ADDED Requirements

### Requirement: Automatic discovery of identifiers
The system SHALL fill identifiers that are missing or `TODO` by querying the user's already-authenticated CLIs (gcloud and bq, snow, databricks), MUST NOT overwrite an existing value, MUST NOT store secrets, and SHALL treat any discovery failure as non-fatal.

#### Scenario: Missing project id
- **WHEN** a BigQuery environment has `project: TODO` and gcloud has a configured project
- **THEN** the catalog is updated with that project id and the connection document is regenerated

#### Scenario: User value present
- **WHEN** an identifier already has a value
- **THEN** discovery leaves it untouched
