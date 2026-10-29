# Diagramas (Mermaid)

Fuentes en `docs/diagrams/*.mmd`; GitHub los dibuja aquí. Verde = no cuesta llamadas a Claude; naranja = sí cuesta. Para regenerar PNG: `npx @mermaid-js/mermaid-cli -i docs/diagrams/NN-x.mmd -o NN-x.png -c docs/diagrams/mermaid-config.json -w 2400 -s 2`.

## Arquitectura: quién llama a quién

```mermaid
flowchart LR
  subgraph MAC["Tu Mac"]
    direction TB
    MD["Repo del proyecto<br/>docs/agent-memory (Git)"]
    CC["Claude Code<br/>plugin · skills · hooks"]
    OBS["Observer :8017<br/>claude -p haiku"]
  end
  subgraph DK["Docker · agents_memory_net"]
    direction TB
    MCP["Cognee MCP :45873"]
    API["Cognee API :45874"]
    PG[("Postgres + pgvector<br/>schema ds_ por dataset")]
    GR[("Grafo Ladybug<br/>.lbug por dataset")]
  end
  MD -->|"sync por hash"| API
  CC -->|"hooks HTTP"| API
  CC -->|"MCP recall"| MCP
  MCP --> API
  API --> PG
  API --> GR
  API -->|"host.docker.internal<br/>token Bearer"| OBS
  classDef mac fill:#E0F2EE,stroke:#176B7B,color:#12202B
  classDef dock fill:#E8EEF7,stroke:#3B5B8C,color:#12202B
  class CC,OBS,MD mac
  class API,MCP,PG,GR dock
```

## Flujo de escritura

```mermaid
flowchart LR
  A["Markdown<br/>en Git"] --> C{"¿Cambió<br/>el hash?"}
  C -->|"no"| Z["Nada<br/>0 llamadas"]
  C -->|"sí"| D["Reemplazar:<br/>borrar + add"]
  D --> H["cognify<br/>observer → Claude"]
  H --> I{"¿Se recupera<br/>el documento?"}
  I -->|"sí"| J["indexed"]
  I -->|"no"| K["reintento<br/>sin duplicar"]
  classDef free fill:#E0F2EE,stroke:#176B7B,color:#12202B
  classDef cost fill:#FCE9D2,stroke:#C96A12,color:#12202B
  class Z,J free
  class H cost
```

## Flujo de lectura

```mermaid
flowchart LR
  B["Abrir sesión:<br/>briefing automático"] --> A{"¿Basta con el<br/>briefing y CLAUDE.md?"}
  A -->|"sí"| R["Responder"]
  A -->|"no"| C["recall CHUNKS<br/>0 llamadas"]
  C --> G{"¿Las fuentes<br/>cambiaron en Git?"}
  G -->|"no"| R
  G -->|"sí"| H["Abrir solo<br/>esos archivos"] --> R
  classDef free fill:#E0F2EE,stroke:#176B7B,color:#12202B
  class B,C,R free
```

## Ciclo de un día de trabajo

```mermaid
flowchart LR
  A["Abrir:<br/>briefing"] --> C["Trabajo"]
  C --> D{"¿Hito<br/>terminado?"}
  D -->|"no"| C
  D -->|"sí"| E["Handoff +<br/>sync"]
  E --> G["Cerrar:<br/>checkpoint"]
  G --> I["improve final<br/>≈3 llamadas"]
  I -.->|"mañana"| A
  classDef free fill:#E0F2EE,stroke:#176B7B,color:#12202B
  classDef cost fill:#FCE9D2,stroke:#C96A12,color:#12202B
  class A,G free
  class E,I cost
```

## Dónde se paga la historia de sesiones

```mermaid
flowchart LR
  T["Cada turno<br/>0 llamadas"] --> CA["Caché de sesión<br/>sin TTL"]
  CA --> IMP["Cierre: improve<br/>lo lanza el plugin"]
  IMP -->|"topes 1 + 1"| LLM["≈3 llamadas<br/>a Claude"]
  LLM --> GR["Grafo del<br/>dataset"]
  GR --> REC["Sesión nueva:<br/>recall lo recupera"]
  CAP["COGNEE_CAPTURE=false"] -.->|"único interruptor"| IMP
  classDef free fill:#E0F2EE,stroke:#176B7B,color:#12202B
  classDef cost fill:#FCE9D2,stroke:#C96A12,color:#12202B
  class T,CA,REC free
  class IMP,LLM cost
```
