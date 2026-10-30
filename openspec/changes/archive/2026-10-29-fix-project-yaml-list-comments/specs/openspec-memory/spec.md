## ADDED Requirements

### Requirement: Contract sources tolerate comments
The system SHALL ignore trailing `# comments` on every line of `.agent-memory/project.yaml`, list items included, so that the shipped template indexes OpenSpec specs and changes.

#### Scenario: Commented source line
- **WHEN** a source is written as `- openspec/specs/**/*.md   # current specs`
- **THEN** the pattern used is `openspec/specs/**/*.md` and its files are indexed
