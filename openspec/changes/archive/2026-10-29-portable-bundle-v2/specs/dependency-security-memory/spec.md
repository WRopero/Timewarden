## ADDED Requirements

### Requirement: Version inventory
The system SHALL maintain, per project, the inventory of direct dependencies with the version resolved in the lockfiles (Poetry, npm, pinned requirements) and the runtime versions declared in Dockerfiles.

#### Scenario: Unchanged lockfile
- **WHEN** a session is opened and the lockfiles have not changed
- **THEN** the inventory is not modified and no files are written

### Requirement: Change history with reason
When a version changes, the system SHALL record the date, package, previous and new version, commit, and reason (`security` if the latest lockfile commit mentions a CVE, GHSA, or vulnerability; `upgrade` otherwise) and MUST allow changes to be annotated manually.

#### Scenario: Security fix
- **WHEN** a commit bumps `brotli` and its message cites a CVE
- **THEN** the history marks the change as `security` and stores the identifier

### Requirement: Automatic vulnerability audit
When a session starts, the system SHALL launch in the background, at most once every 24 hours, an audit against a public vulnerability database using the exact versions from the lockfiles. Startup MUST NOT wait for the audit and, when offline, MUST fail silently while logging the error.

#### Scenario: Recent audit
- **WHEN** the last audit is less than 24 hours old
- **THEN** the network is not queried

#### Scenario: No network
- **WHEN** there is no connection
- **THEN** the session starts normally and the briefing indicates that the last attempt failed

### Requirement: Visible security backlog
The startup briefing SHALL show the number of open vulnerabilities, how many are high or critical, and the most severe ones along with the version that fixes them, and the system SHALL write the full list as pending checkboxes in an indexable memory document. It MUST be possible to accept a risk by listing its identifier in an exceptions file.

#### Scenario: Critical vulnerability in a direct dependency
- **WHEN** the audit finds a critical vulnerability in a direct package
- **THEN** it appears first in the briefing with the fixed version

#### Scenario: Accepted risk
- **WHEN** an identifier is in the exceptions file
- **THEN** it is neither counted nor listed
