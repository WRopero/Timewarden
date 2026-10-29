## ADDED Requirements

### Requirement: Per-environment deployment ledger
The system SHALL store, per environment, the deployed commit, the date, and a note, and SHALL record a deployment only on explicit request after verifying its health.

#### Scenario: Recording after verification
- **WHEN** the agent deploys and the health check passes
- **THEN** it runs the recording step with the deployed commit

### Requirement: Per-branch status
The briefing SHALL indicate how many commits from the main branch are still awaiting deployment and, for the current branch, whether it has been merged into the main branch and whether it has been deployed.

#### Scenario: Open branch
- **WHEN** the current branch has commits that are not in the main branch
- **THEN** the briefing marks it as not merged and not deployed

#### Scenario: Unknown commit
- **WHEN** the recorded commit does not exist in the local clone
- **THEN** the briefing warns that it must be verified
