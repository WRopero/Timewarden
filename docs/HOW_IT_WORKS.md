# How it works

The graphs are Mermaid: GitHub renders them directly. Colors: **green** = does not spend Claude tokens; **orange** = does.

## 1. Overview
```mermaid
flowchart LR
  subgraph REPO["Your repository"]
    MD["docs/agent-memory<br/>Markdown in Git"]
    OS["openspec/<br/>specs and changes"]
    CTR[".agent-memory/<br/>contract, deployments, dependencies"]
  end
  subgraph LOCAL["Your machine, 127.0.0.1 only"]
    HOOKS["Claude Code hooks<br/>briefing and checkpoint"]
    DK["Docker: Cognee, Postgres + pgvector, MCP"]
    OBS["Observer<br/>claude -p"]
    PANEL["Management Memory panel"]
  end
  CC["Claude Code"]
  MD -->|"incremental sync"| DK
  OS -->|"incremental sync"| DK
  DK -->|"summarize on index"| OBS
  HOOKS -->|"reads Markdown and Git"| CC
  CC -->|"MCP recall"| DK
  DK --> PANEL
  classDef free fill:#E3F1E4,stroke:#3C7A45,color:#1F2A1F
  classDef paid fill:#FBE7D2,stroke:#C25B12,color:#2A190D
  class HOOKS,CC,PANEL,MD,OS,CTR,DK free
  class OBS paid
```
**Principle:** the Markdown in Git is the source of truth; Cognee is a derived index (it can be rebuilt). Querying is free; indexing costs.

## 2. Agent-guided installation
```mermaid
flowchart TD
  A["You paste AGENT_PROMPT.md to an agent"] --> B["seed.sh doctor<br/>requirements and OpenSpec"]
  B --> C{"Language clear?"}
  C -->|"no, exit 3"| C2["The agent asks you es or en"] --> D
  C -->|"yes"| D{"Project type clear?"}
  D -->|"no, exit 3"| D2["The agent asks you<br/>dbt, Dataform, Snowflake, BigQuery..."] --> E
  D -->|"yes"| E["seed.sh machine<br/>Docker, observer, keys"]
  E --> F["seed.sh project<br/>contract, CLAUDE.md, hooks, skills, OpenSpec"]
  F --> G["Pilot corpus<br/>skill project-memory-bootstrap"]
  G --> H["memctl sync --apply<br/>indexes, spends tokens, asks for approval"]
  H --> I["seed.sh panel and verify"]
```

## 3. Lifecycle of a session
```mermaid
sequenceDiagram
  participant U as You
  participant CC as Claude Code
  participant H as Hooks
  participant M as Cognee Memory
  U->>CC: you open a session in the repo
  CC->>H: SessionStart
  H->>H: briefing (Markdown + Git) and logs version changes
  H-->>CC: briefing injected, without querying Cognee
  H->>H: launches OSV audit in the background if 24 h have passed
  U->>CC: you ask for something ambiguous
  CC->>M: recall CHUNKS top_k 3, before deciding or asking
  M-->>CC: fragments with path and status
  CC->>CC: verifies freshness with memory_stale, no tokens
  U->>CC: you close or compact
  CC->>H: SessionEnd or PreCompact
  H->>H: checkpoint auto-rama.md
```

## 4. What the briefing contains
```mermaid
flowchart LR
  P["project.md<br/>goal"] --> B["Briefing<br/>max. 6000 characters"]
  D["decisions/<br/>current"] --> B
  R["business/<br/>rules"] --> B
  T["open to-dos"] --> B
  DP["Deployments<br/>by environment and branch"] --> B
  S["Security<br/>open vulnerabilities"] --> B
  O["OpenSpec<br/>active changes"] --> B
  C["Checkpoint of the<br/>current branch"] --> B
  HR["Last real handoff"] --> B
  ST["Stale notes"] --> B
```
The cap trims the body, never the footer with the usage instructions.

## 5. Automatic security audit
```mermaid
flowchart TD
  S["SessionStart"] --> SN["memory_deps snapshot<br/>reads lockfiles"]
  SN --> CH{"Did any version change?"}
  CH -->|"yes"| LOG["Logs in dependencies.json<br/>reason: security if the commit cites CVE or GHSA, otherwise upgrade"]
  CH -->|"no"| AGE
  LOG --> AGE{"Last audit more than 24 h ago?"}
  AGE -->|"no"| SHOW
  AGE -->|"yes"| BG["memory_audit run<br/>detached process, non-blocking"]
  BG --> OSV["api.osv.dev<br/>name and version only"]
  OSV --> RES["Result outside the repo"]
  RES --> DOC["docs/agent-memory/security/dependencies.md<br/>pending checkboxes"]
  RES --> SHOW["Briefing: open, high and critical,<br/>fixing version"]
  OSV -.->|"no network"| FAIL["Fails silently and notes it"]
```

## 6. Deployments and branches
```mermaid
flowchart TD
  X["You deploy to an environment"] --> V{"Health verified?"}
  V -->|"no"| NO["Nothing is recorded"]
  V -->|"yes"| REC["memory_deploy record<br/>environment, commit, note"]
  REC --> ST["In the next briefing"]
  ST --> Q1["Commits on the main branch<br/>not yet deployed"]
  ST --> Q2{"Current branch"}
  Q2 -->|"merged into main"| Q3["Deployed if it is an ancestor<br/>of what was deployed"]
  Q2 -->|"not merged"| Q4["Marked NOT deployed<br/>with its own commits"]
```
In data projects, "deployed" means the production job/release finished successfully on that commit.

## 7. OpenSpec drives the changes
```mermaid
flowchart LR
  I["Idea or request"] --> M{"Ambiguous?"}
  M -->|"yes"| REC["Consult memory<br/>and current specs"]
  M -->|"no"| P
  REC --> P["/opsx:propose<br/>proposal, specs, design, tasks"]
  P --> RV["User review"]
  RV --> AP["/opsx:apply<br/>implements the tasks"]
  AP --> AR["/opsx:archive<br/>current specs are updated"]
  AR --> SY["memctl sync<br/>specs enter the memory"]
```
Exceptions with no change: typos, formatting, comments, and urgent hotfix (documented afterward with a change).

## 8. Project type detection
```mermaid
flowchart TD
  R["Repository"] --> E["Looks for evidence<br/>dbt_project.yml, workflow_settings.yaml, .sqlx,<br/>Terraform google_bigquery, package.json, manage.py..."]
  E --> L{"Detected layers"}
  L -->|"one clear combination"| OK["dbt+snowflake, dbt+bigquery,<br/>dataform+bigquery, bigquery, webapp..."]
  L -->|"dbt without adapter, two warehouses,<br/>empty repo"| ASK["Exit 2: the agent asks<br/>with the options"]
  ASK --> FORCE["--profile layers"]
  OK --> APPLY["Rules in CLAUDE.md and indexing exclusions"]
  FORCE --> APPLY
```
For the detailed architecture diagrams (write, read, continuity, history) see [`diagrams.md`](diagrams.md).
