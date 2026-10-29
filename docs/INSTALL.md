# How to Install Timewarden

There are two paths: **with an agent** (recommended: it detects the language and project type and asks you about anything ambiguous) or **by hand**. In both cases the installation has two levels: **once per machine** (the stack) and **once per repository** (the contract, the hooks, the skills, and OpenSpec).

## 0. Requirements
| You need | How to check |
|---|---|
| macOS with Docker Desktop open (the only validated platform) | `docker info` |
| Claude Code ≥ 2.1.287, signed in | `claude --version` |
| Python 3 and git | `python3 --version`, `git --version` |
| OpenSpec (CLI) | `openspec --version`. If missing: `curl -fsSL https://raw.githubusercontent.com/Fission-AI/OpenSpec/main/scripts/binary/install.sh \| sh` (review the script before running it) or `npm i -g @fission-ai/openspec` |
| ~10 GB free and internet access the first time | Docker images and the embeddings model (~640 MB) |
`seed-bundle/seed.sh doctor` checks all of this and changes nothing.

## 1. Get the kit
```bash
git clone https://github.com/<your-username>/Timewarden.git      # or unzip the release .zip
cd Timewarden
```
It can live in **any folder**: paths are resolved from its location, and each repo stores its own in `.agent-memory/local.yaml` (not versioned).

## 2. Path A — with an agent (recommended)
Open Claude Code and paste the block from [`seed-bundle/AGENT_PROMPT.md`](../seed-bundle/AGENT_PROMPT.md), replacing `<KIT>`, `<repo>`, and `<project_id>`. The agent follows [`seed-bundle/SEED.md`](../seed-bundle/SEED.md): it asks before starting containers, installing the plugin, bringing up the panel, or indexing, and **it asks you for the language and project type if they are not obvious**.

## 3. Path B — by hand
```bash
# 3.1 Once per machine
seed-bundle/seed.sh doctor                    # requirements
seed-bundle/seed.sh machine --yes             # observer + Docker + keys + ~/.cognee/.env + observer LaunchAgent

# 3.2 Once per repository
seed-bundle/seed.sh project /path/to/repo my-project --lang auto --profile auto --with-plugin
#   --lang auto      detects es/en; if ambiguous it exits with code 3 -> use --lang es|en
#   --profile auto   detects the type (dbt, dataform, snowflake, bigquery, webapp...); ambiguous -> code 3 -> use --profile dbt,snowflake
#   --no-openspec    skips OpenSpec (not recommended: it is part of the method)
#   --no-capture     does not capture sessions (briefing and recall only)
#   --with-plugin    installs the plugin and the MCP at the repo scope (otherwise it prints the commands)

# 3.3 Initial corpus: in Claude Code, inside the repo, ask it to use the project-memory-bootstrap skill
#     (it reads the real documentation and proposes 10-20 documents; review them and mark verified only what you have checked)

# 3.4 Index (spends tokens from your subscription: ~2 calls per chunk)
scripts/memctl.sh sync /path/to/repo              # plan: 0 calls
scripts/memctl.sh sync /path/to/repo --apply

# 3.5 Panel and verification
seed-bundle/seed.sh panel --yes                   # http://127.0.0.1:45876
seed-bundle/seed.sh verify /path/to/repo
```

### Exit codes you should know
| Code | Meaning | What to do |
|---|---|---|
| 3 | Ambiguous language or project type | Answer the question and repeat with `--lang` / `--profile` |
| 4 | The `openspec` CLI is missing with `--openspec yes` | Install OpenSpec |
| ≠ 0 in `doctor` | A requirement is missing | Read the `MISSING` line |

## 4. What you should see when finished
- `seed.sh verify` all green: API ready, observer authenticated and reachable from a container, panel on :45876, project contract, briefing ≤ 6000 characters, MCP `agents_cognee` connected.
- When you open a new session in the repo, the briefing appears on its own (goal, decisions, deployments, security, OpenSpec changes, branch checkpoint).
- `scripts/memctl.sh eval <repo>` with 20 questions (see [`evals/README.md`](../evals/README.md)): goal ≥ 85% recall@5.

## 5. More projects, another machine, updating, uninstalling
- **Another repository:** repeat only step 3.2 (and 3.3–3.5) with a different `project_id`. The stack is shared.
- **Another machine (another PC):** clone or unzip the kit there and repeat everything. **The memory data does not travel:** it lives in Docker on each machine. What is shared between people is the versioned Markdown in the repo (`docs/agent-memory/`, `openspec/`, `.agent-memory/`); each person runs `memctl.sh sync <repo> --apply` and rebuilds their index.
- **Updating the kit:** `git pull` (or the new `.zip`) and `seed.sh verify`. Image versions are pinned in `config/versions.lock`; changing the embeddings model forces a reindex.
- **Stop / pause:** `scripts/memctl.sh stop` (never `docker compose down -v`); to capture less: `COGNEE_CAPTURE=false` in `~/.cognee/.env`.
- **Disconnect a repo:** `claude plugin disable cognee-memory@cognee` and `claude mcp remove agents_cognee`; delete `.agent-memory/`, the section in `CLAUDE.md`, and the hooks in `.claude/settings.local.json`.

## 6. Common problems
| Symptom | Likely cause | Fix |
|---|---|---|
| `doctor`: Docker is not running | Docker Desktop is closed | Open it |
| The API never reaches `ready` | First model download (60–90 s or more) | Wait; `docker logs agents_cognee_api` |
| `observer not reachable from Docker` | Observer is down, or token issue | `scripts/observer.sh start` and `probe` |
| After restarting the machine nothing responds | Observer has no LaunchAgent | `scripts/observer_launchagent.sh install` |
| `recall` returns 404 | Incorrect dataset name | Copy `memory_dataset` literally from `project.yaml` (string, not list) |
| The agent does not see the briefing | Hooks not installed, or project without `.agent-memory/project.yaml` | Redo step 3.2 and open a new session |
| Port in use | Another service on 45873–45876 / 8017 | Free it; the kit only publishes on `127.0.0.1` |
The full troubleshooting table is in [`seed-bundle/spec/Cognee-memory-specification.md`](../seed-bundle/spec/Cognee-memory-specification.md) §21.7.
