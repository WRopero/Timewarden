## MODIFIED Requirements

### Requirement: Specs and changes as memory
If the repository uses OpenSpec, the system SHALL index `openspec/specs` as current knowledge and `openspec/changes` (active and archived) as proposals and their history, without requiring frontmatter. Files under `openspec/changes`, including their delta specs, SHALL take their change's label and never that of a current spec.

#### Scenario: Current spec
- **WHEN** a file exists at `openspec/specs/<capacidad>/spec.md`
- **THEN** it is indexed as type `openspec-spec` with status `verified`

#### Scenario: Active change
- **WHEN** a non-archived change exists
- **THEN** all its files, delta specs included, are indexed as type `openspec-change` with status `draft`

#### Scenario: Archived change
- **WHEN** a change is archived
- **THEN** all its files, delta specs included, are indexed as type `openspec-change-archived` with status `verified`

#### Scenario: Label changes
- **WHEN** a document's type or status changes but its content does not
- **THEN** the next sync re-indexes it so the stored chunk carries the new label
