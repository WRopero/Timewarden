# openspec-memory Specification

## Purpose
Integrate OpenSpec into the installation as the mandatory director of changes and as an indexed part of the project memory.

## Requirements

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

### Requirement: Summary in the briefing
The briefing SHALL list the number of current specs and the names of the active changes.

#### Scenario: No active changes
- **WHEN** there are no active changes
- **THEN** the briefing states this explicitly

### Requirement: OpenSpec is part of the installation
The installer SHALL check for the presence of the OpenSpec CLI, initialize it in the project repository (using the project's language) unless the user declines, and report with a specific exit code if the CLI is missing when it is required.

#### Scenario: CLI present
- **WHEN** the memory is installed in a repository without `openspec/` and the CLI is available
- **THEN** the repository ends up with OpenSpec initialized and the workflow commands available

#### Scenario: CLI absent and required
- **WHEN** the CLI is not installed and OpenSpec is required
- **THEN** the installation ends with the exit code reserved for "OpenSpec missing" and explains how to install it

### Requirement: OpenSpec directs every change
The instructions left by the installer SHALL establish that any new functionality, behavior change, non-trivial refactor, or data/infrastructure change is carried out through an OpenSpec change (propose, user review, implement, archive), with exceptions limited to typos, formatting, comments, and urgent hotfixes documented afterward.

#### Scenario: Request for a feature
- **WHEN** the user asks for a new feature
- **THEN** the agent creates a change proposal and waits for review before writing product code

#### Scenario: Typo
- **WHEN** the change is a text typo
- **THEN** the agent applies it without creating a change
