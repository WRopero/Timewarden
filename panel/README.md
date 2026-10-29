# Management Memory

Internal, **read-only** control panel for monitoring project memory (Cognee in Docker): service health, which vectors exist and where, graph, PostgreSQL, tokens and cost (observer + OpenTelemetry), API calls, containers, and knowledge base size per project (with warnings to help decide what to compact or delete). It doesn't modify anything.

Runs at `http://127.0.0.1:45876`, local only.

## How to run it

The `.env` (0600) is generated on each machine with `scripts/setup.py` and is in `.gitignore`: the code contains no secrets.

Requirements: Docker Desktop running and the memory stack up (this panel ships inside the **Timewarden** kit, folder `panel/`; see `seed-bundle/SEED.md`). The panel connects to that stack, so without it there is nothing to show.

```bash
cd <KIT>/panel

# First time (idempotent, doesn't print secrets): creates .env, the read-only Postgres role and the registry copy
python3 scripts/setup.py

# Start (builds the image the first time)
docker compose up -d --build

open http://127.0.0.1:45876
```

| Action | Command |
|---|---|
| View logs | `docker compose logs -f mm_app` |
| Stop | `docker compose stop` (never `down -v`; it has no volumes of its own to lose) |
| Rebuild after changing code | `docker compose up -d --build mm_app` |
| Tests | `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest` |

If the browser shows an old version after rebuilding: force reload (`Cmd+Shift+R`).

## What each section shows
Summary · Knowledge bases (per project/dataset, rebuild cost, heaviest documents, warnings) · Vectors (what is stored and where) · Graph · PostgreSQL (explorer + SELECT console) · Search (retrieval test) · **Memory usage** (when the briefing is injected and when it is queried, with result and verdict "does it work?") · **Machine resources** (CPU/RAM/swap/disk of the Mac on demand and of Docker) · Tokens and cost · API and containers · Synchronization · Guide and glossary (explains each concept in plain language).

## Data that comes from the Mac (lightweight services, in `agents_memory_system`)
- **Memory usage**: `scripts/usage_scan.py` reads the Claude Code transcripts (read-only, metadata only) and writes `view/usage.jsonl`; it is refreshed when each session closes (hook) or manually.
- **Machine resources**: a container can't see the Mac. `scripts/host_stats_launchagent.sh install` registers a launchd socket activation (`127.0.0.1:8018`): **there is no resident process**; only when you click "Measure the Mac now" does launchd run `host_stats.py --inetd` once (~2 s). Docker is read from the engine through the read-only proxy (`/info`, `/system/df`).

## Tokens: what is measured and what is not
1. **Observer** (`~/.cognee-plugin/observer`): everything Cognee spends when indexing. Complete.
2. **Claude Code via OpenTelemetry**: only sessions opened with `<KIT>/scripts/claude-memory <project>` (real `OTEL_*` variables; the `env` block in `settings.json` does **not** work). Suggestion: `alias cm='<KIT>/scripts/claude-memory'`.
3. **Cognee session statistics**: usually 0 (the observer uses the subscription).
The remaining subscription quota can't be queried from outside.

## Security (by design)
- `127.0.0.1` only; Host middleware (anti DNS-rebinding), strict CSP, `X-Frame-Options`, `no-store`.
- PostgreSQL with the `mm_reader` role: read-only transactions, 15 s limit, a single `SELECT/WITH/EXPLAIN/SHOW/VALUES/TABLE` statement.
- Docker only via `socket-proxy` with an allowlist (GET for logs/stats/inspect); the panel doesn't mount the socket.
- Non-root container, `cap_drop ALL`, data volumes read-only.
- All dynamic text is inserted with `textContent`, never `innerHTML`.
- `.env` (0600) is not versioned.

## Structure
`app/` FastAPI (`main.py` endpoints; `pg.py`, `otel.py`, `observer.py`, `kb.py`, `vectors.py`, `dockerapi.py`, `storage.py`, `cognee_client.py`) · `static/` SPA with no build step (vanilla JS + cytoscape vendored at build time) · `scripts/setup.py` · `compose.yaml` · `tests/`.

## Extending it
A new endpoint = a function in `app/` + a route in `app/main.py` + a page in `static/app.js` (`pages.<key>`, and the `NAV`/`NAMES` menu). Keep everything read-only and the texts in plain language; add the new terms to the `GLOSSARY`.

## Installing it on another machine
The kit installs it (phase 7 of `seed-bundle/SEED.md`): `seed-bundle/seed.sh panel --yes`.
