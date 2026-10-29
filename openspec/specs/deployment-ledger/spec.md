# deployment-ledger Specification

## Purpose
Record which commit is deployed per environment and show the status of each branch relative to what is deployed.

## Requirements

### Requirement: Deployment registration per environment
The system SHALL store, per environment, the deployed commit, the date, and a note, and SHALL register a deployment only upon explicit request after verifying its health.

#### Scenario: Registration after verification
- **WHEN** the agent deploys and the health check passes
- **THEN** it runs the registration with the deployed commit

### Requirement: Status per branch
The briefing SHALL indicate how many commits from the main branch remain to be deployed and, for the current branch, whether it is merged into the main branch and whether it is deployed.

#### Scenario: Open branch
- **WHEN** the current branch has commits that are not in the main branch
- **THEN** the briefing marks it as not merged and not deployed

#### Scenario: Unknown commit
- **WHEN** the registered commit does not exist in the local clone
- **THEN** the briefing warns that it must be verified
