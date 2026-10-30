## ADDED Requirements

### Requirement: Unattended installation
The runbook and the prompt SHALL instruct the agent to execute every phase without asking the user for approval (containers, plugin, project setup, indexing, panel, verification) and to report what it did and what indexing cost at the end, and MUST still stop and ask only when the language or project type is ambiguous (exit code 3) or the operating system is not validated.

#### Scenario: Fresh machine and repository
- **WHEN** the user hands the kit and a repository to the agent
- **THEN** the agent completes machine, project, corpus, index, panel and verify phases with no further input and delivers the report

#### Scenario: Ambiguous project type
- **WHEN** the detector cannot decide the project type
- **THEN** the agent asks that single question and continues unattended afterwards

## MODIFIED Requirements

### Requirement: Runbook and verification
The package SHALL include the phased runbook (executed by the agent without approval checkpoints), the prompt to paste into an agent, the technical specification, and an acceptance check, and MUST document what leaves the user's machine (only the text that is indexed via Claude).

#### Scenario: Delivery
- **WHEN** a colleague receives the `.zip`
- **THEN** they find a `LEEME` with the minimal steps and the ready-made prompt, without knowing the system
