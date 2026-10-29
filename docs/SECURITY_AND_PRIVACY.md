# Security and privacy

## What leaves your machine
| Data | Destination | When |
|---|---|---|
| Fragments of your memory documents | Claude (your subscription), via the observer | Only when **indexing** and when reading retrieved text in the conversation |
| Package names and versions | `api.osv.dev` | Vulnerability audit, at most every 24 h |
| Nothing else | — | Embeddings, search, graph, database, and dashboard are 100% local |

## Network surface
All ports are published only on `127.0.0.1` (45873–45876 and 8017). The dashboard adds `Host` validation (anti DNS-rebinding), a strict CSP, `X-Frame-Options`, and `no-store`, and it does not mount the Docker socket: it uses a read-only proxy with an allowlist.

## Secrets
- The stack's secrets are generated per machine (mode 0600) and are not versioned; the dashboard's `.env` isn't either.
- The dashboard's database role (`mm_reader`) is read-only, with a 15 s limit and a single `SELECT/WITH/EXPLAIN/SHOW/VALUES/TABLE` statement.
- Profiles exclude `.env*`, `profiles.yml`, keys, service accounts, and Terraform state from indexing.
- Never store credentials or real sensitive data in the memory documents.

## Forbidden (also for the agent)
`docker compose down -v`, `forget` with `everything`, mounting the observer's directory into a container, publishing ports outside `127.0.0.1`, running against production without approval.

## Isolation between projects
Each project has its own dataset (`<id>-knowledge`, `<id>-sessions`) and `cross_project_recall: false` by default.

## Threat model, in short
This is a local, single-user tool: it protects against accidental leaks (ports, secrets in memory, destructive SQL from the dashboard), not against an attacker with access to your machine account.
