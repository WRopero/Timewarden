## Why

The installation is run by the agent on behalf of the user, yet the runbook still stops for approvals and leaves manual steps: starting containers, installing the plugin, bringing up the panel, the first indexing, filling `TODO` identifiers in the connection catalog, and enabling live metadata. The user's requirement is that installing Timewarden requires nothing manual from them.

## What Changes

- The runbook and the prompt to paste become **unattended**: the agent runs every phase (machine, project with plugin, corpus, index, panel, verify) without asking for approval, and reports cost and what it did at the end. It still stops for genuinely ambiguous input (language or project type, exit code 3) and for unvalidated operating systems.
- `seed.sh project` installs the plugin by default (`--no-plugin` to skip) and, for data projects, runs the graph/catalog setup and first indexing; new `seed.sh index`.
- Connection catalog: `discover` fills `TODO` identifiers by asking the user's own authenticated CLIs (gcloud/bq, snow, databricks); `enable-live` probes each environment with a read-only metadata call and turns `metadata_sync` on where it works, with a 24 h retry backoff on failure.
- The sync runs discovery and enablement itself, and the first indexing of the graph documents now runs automatically in the background (cap `max_baseline_docs`, default 60 per run) instead of waiting for a manual command. Switches: `auto_baseline`, `auto_enable_live`.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `portable-bundle`: the runbook is unattended; the agent no longer waits for approval checkpoints.
- `data-system-sync`: live metadata enablement and first indexing happen automatically.
- `data-connection-catalog`: identifiers are discovered and live metadata is enabled automatically.

## Impact

`seed-bundle/*` (SEED.md, AGENT_PROMPT.md, manifest.yaml, seed.sh), `scripts/data_connect.py`, `scripts/data_sync.py`, `scripts/data_sources.py`, `scripts/install_project.py`, docs, tests. Trade-off accepted by the user: installation spends Claude tokens for the first indexing without asking first; the cost is reported at the end and the guard rails (read-only, metadata only, never table data, no secrets) are unchanged.
