# Diagrams (Mermaid)

Sources in `docs/diagrams/*.mmd`; GitHub renders them here. Green = costs no calls to Claude; orange = does cost calls. To regenerate PNG: `npx @mermaid-js/mermaid-cli -i docs/diagrams/NN-x.mmd -o NN-x.png -c docs/diagrams/mermaid-config.json -w 2400 -s 2`.

## Architecture: who calls whom

```mermaid
flowchart LR
  subgraph MAC["Your Mac"]
    direction TB
    MD["Project repo<br/>docs/agent-memory (Git)"]
    CC["Claude Code<br/>plugin · skills · hooks"]
    OBS["Observer :8017<br/>claude -p haiku"]
  end
  subgraph DK["Docker · agents_memory_net"]
    direction TB
    MCP["Cognee MCP :45873"]
    API["Cognee API :45874"]
    PG[("Postgres + pgvector<br/>ds_ schema per dataset")]
    GR[("Ladybug graph<br/>.lbug per dataset")]
  end
  MD -->|"hash sync"| API
  CC -->|"HTTP hooks"| API
  CC -->|"MCP recall"| MCP
  MCP --> API
  API --> PG
  API --> GR
  API -->|"host.docker.internal<br/>Bearer token"| OBS
  classDef mac fill:#E0F2EE,stroke:#176B7B,color:#12202B
  classDef dock fill:#E8EEF7,stroke:#3B5B8C,color:#12202B
  class CC,OBS,MD mac
  class API,MCP,PG,GR dock
```

## Write flow

```mermaid
flowchart LR
  A["Markdown<br/>in Git"] --> C{"Did the<br/>hash change?"}
  C -->|"no"| Z["Nothing<br/>0 calls"]
  C -->|"yes"| D["Replace:<br/>delete + add"]
  D --> H["cognify<br/>observer → Claude"]
  H --> I{"Is the document<br/>retrieved?"}
  I -->|"yes"| J["indexed"]
  I -->|"no"| K["retry<br/>without duplicating"]
  classDef free fill:#E0F2EE,stroke:#176B7B,color:#12202B
  classDef cost fill:#FCE9D2,stroke:#C96A12,color:#12202B
  class Z,J free
  class H cost
```

## Read flow

```mermaid
flowchart LR
  B["Open session:<br/>automatic briefing"] --> A{"Are the briefing<br/>and CLAUDE.md enough?"}
  A -->|"yes"| R["Answer"]
  A -->|"no"| C["recall CHUNKS<br/>0 calls"]
  C --> G{"Did the sources<br/>change in Git?"}
  G -->|"no"| R
  G -->|"yes"| H["Open only<br/>those files"] --> R
  classDef free fill:#E0F2EE,stroke:#176B7B,color:#12202B
  class B,C,R free
```

## A working day cycle

```mermaid
flowchart LR
  A["Open:<br/>briefing"] --> C["Work"]
  C --> D{"Milestone<br/>done?"}
  D -->|"no"| C
  D -->|"yes"| E["Handoff +<br/>sync"]
  E --> G["Close:<br/>checkpoint"]
  G --> I["final improve<br/>≈3 calls"]
  I -.->|"tomorrow"| A
  classDef free fill:#E0F2EE,stroke:#176B7B,color:#12202B
  classDef cost fill:#FCE9D2,stroke:#C96A12,color:#12202B
  class A,G free
  class E,I cost
```

## Where the session history is paid for

```mermaid
flowchart LR
  T["Every turn<br/>0 calls"] --> CA["Session cache<br/>no TTL"]
  CA --> IMP["Close: improve<br/>launched by the plugin"]
  IMP -->|"caps 1 + 1"| LLM["≈3 calls<br/>to Claude"]
  LLM --> GR["Dataset<br/>graph"]
  GR --> REC["New session:<br/>recall retrieves it"]
  CAP["COGNEE_CAPTURE=false"] -.->|"only switch"| IMP
  classDef free fill:#E0F2EE,stroke:#176B7B,color:#12202B
  classDef cost fill:#FCE9D2,stroke:#C96A12,color:#12202B
  class T,CA,REC free
  class IMP,LLM cost
```
