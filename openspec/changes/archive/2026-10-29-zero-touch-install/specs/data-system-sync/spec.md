## ADDED Requirements

### Requirement: Automatic live enablement and first indexing
The sync SHALL, without user action, discover missing identifiers, probe each environment with a read-only metadata call and enable `metadata_sync` where the probe succeeds (retrying failures no sooner than every 24 hours), and SHALL start the first indexing of the generated documents in the background, capped per run, unless the user disables it with `auto_enable_live: false` or `auto_baseline: false`.

#### Scenario: Authenticated CLI
- **WHEN** a session starts in a data project whose warehouse CLI is authenticated
- **THEN** missing identifiers are filled, live metadata is enabled and mirrored, and no manual step is needed

#### Scenario: Broken login
- **WHEN** the probe fails
- **THEN** the environment stays disabled, the reason is reported in the briefing, and the probe is not repeated within 24 hours
