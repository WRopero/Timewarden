# ambiguity-recall-rule Specification

## Purpose
Make the agent consult memory before deciding, assuming, or asking when a task is ambiguous.

## Requirements

### Requirement: Consult before deciding
The instructions that the installer leaves in the project SHALL direct the agent, when faced with an unclear requirement, a design decision, or a "why is it like this", to consult memory (including the OpenSpec specs) and verify its freshness before deciding, assuming, or asking.

#### Scenario: Ambiguous requirement
- **WHEN** the agent cannot resolve a requirement with the loaded context
- **THEN** it consults memory and only asks the user if the ambiguity persists

### Requirement: Cost limit
The lookup MUST use chunk-based retrieval (without going through a model) and MUST NOT be repeated for what the briefing already contains.

#### Scenario: Data already in the briefing
- **WHEN** the answer is in the startup briefing
- **THEN** the agent does not consult memory
