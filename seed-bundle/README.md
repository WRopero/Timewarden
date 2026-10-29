# Project Memory Kit (Cognee in Docker + Claude Code)

Installs persistent, verifiable memory for coding agents in any repository: automatic briefing when a session opens, local retrieval (embeddings in Docker, no per-query cost), per-branch checkpoint, deployment log, versions/security with automatic audit, indexing of OpenSpec specs, and a read-only control panel. It includes **profiles for data projects** (dbt + Snowflake, Dataform + BigQuery, BigQuery/Terraform) and for web applications.

| Contents | Purpose |
|---|---|
| `AGENT_PROMPT.md` | The message you paste to an agent to install everything |
| `SEED.md` | Phased runbook: command, expected result, when to ask |
| `../docs/DATA_PROJECTS.md` | What changes in data projects (BigQuery, Dataform, Snowflake, dbt) |
| `../docs/INSTALL.md` | Step-by-step installation for people |
| `seed.sh` | Orchestrator: `doctor`, `machine`, `project`, `panel`, `verify` |
| `manifest.yaml` | Tested versions, ports, phases, prohibitions (machine-readable) |
| `spec/` | Complete technical specification: design, replication (§21), common problems |

## Quick start
```bash
cd <KIT>
seed-bundle/seed.sh doctor                                    # requirements
seed-bundle/seed.sh machine --yes                             # once per machine
seed-bundle/seed.sh project /path/to/repo my-project --lang auto --profile auto
seed-bundle/seed.sh panel --yes                               # panel at http://127.0.0.1:45876
seed-bundle/seed.sh verify /path/to/repo
```
`--lang auto` and `--profile auto` detect the language and project type and, if they aren't clear, **exit with code 3 so the agent asks you**.

## Requirements
macOS with Docker Desktop (the only validated platform), Claude Code ≥ 2.1.287 with a signed-in session, Python 3, git, and an internet connection for the first installation (Docker images, embeddings model ~640 MB, the `cognee-memory` plugin from Cognee's public marketplace).

## Privacy
Everything runs on your machine (ports only on `127.0.0.1`). Only the text that is **indexed** and the retrieved text you read in the conversation go out to Claude; the vulnerability audit sends only package names and versions to `api.osv.dev`. No credentials are stored: the profiles exclude `profiles.yml`, keys, service accounts, and Terraform state.
