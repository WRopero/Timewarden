# portable-bundle Specification

## Purpose
Distribute the kit as a neutral, relocatable, self-contained package that another agent can install on another machine.

## Requirements

### Requirement: Neutrality
The distributable package MUST NOT contain project names, company names, accounts, email addresses, or absolute paths from the source machine, nor secrets, keys, tokens, databases, or evaluations from a specific project.

#### Scenario: Package scan
- **WHEN** the bundle is packaged
- **THEN** a scan for forbidden terms and secret patterns across all files in the `.zip` finds no matches, and packaging fails if there are any

### Requirement: Relocatable and self-contained
The package SHALL be installable in any directory, resolve all paths relative to its own location (with a variable to override it), and include the Management Memory dashboard, so that it does not depend on external repositories or accounts.

#### Scenario: Installation in another directory
- **WHEN** the `.zip` is unzipped into an arbitrary directory and the requirements check is run
- **THEN** the check reports correct paths and does not reference locations on the source machine

### Requirement: Runbook and verification
The package SHALL include the phased runbook with approval checkpoints, the prompt to paste into an agent, the technical specification, and an acceptance check, and MUST document what leaves the user's machine (only the text that is indexed via Claude).

#### Scenario: Delivery
- **WHEN** a colleague receives the `.zip`
- **THEN** they find a `LEEME` with the minimal steps and the ready-made prompt, without knowing the system
