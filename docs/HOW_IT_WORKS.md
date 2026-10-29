# Cómo funciona

Los grafos son Mermaid: GitHub los dibuja directamente. Colores: **verde** = no gasta tokens de Claude; **naranja** = sí.

## 1. Idea general
```mermaid
flowchart LR
  subgraph REPO["Tu repositorio"]
    MD["docs/agent-memory<br/>Markdown en Git"]
    OS["openspec/<br/>specs y cambios"]
    CTR[".agent-memory/<br/>contrato, despliegues, dependencias"]
  end
  subgraph LOCAL["Tu equipo, solo 127.0.0.1"]
    HOOKS["Hooks de Claude Code<br/>briefing y checkpoint"]
    DK["Docker: Cognee, Postgres + pgvector, MCP"]
    OBS["Observer<br/>claude -p"]
    PANEL["Panel Management Memory"]
  end
  CC["Claude Code"]
  MD -->|"sync incremental"| DK
  OS -->|"sync incremental"| DK
  DK -->|"resumir al indexar"| OBS
  HOOKS -->|"lee Markdown y Git"| CC
  CC -->|"MCP recall"| DK
  DK --> PANEL
  classDef free fill:#E3F1E4,stroke:#3C7A45,color:#1F2A1F
  classDef paid fill:#FBE7D2,stroke:#C25B12,color:#2A190D
  class HOOKS,CC,PANEL,MD,OS,CTR,DK free
  class OBS paid
```
**Principio:** el Markdown en Git es la fuente de verdad; Cognee es un índice derivado (se puede reconstruir). Consultar es gratis; indexar cuesta.

## 2. Instalación guiada por un agente
```mermaid
flowchart TD
  A["Pegas AGENT_PROMPT.md a un agente"] --> B["seed.sh doctor<br/>requisitos y OpenSpec"]
  B --> C{"Idioma claro?"}
  C -->|"no, exit 3"| C2["El agente te pregunta es o en"] --> D
  C -->|"si"| D{"Tipo de proyecto claro?"}
  D -->|"no, exit 3"| D2["El agente te pregunta<br/>dbt, Dataform, Snowflake, BigQuery..."] --> E
  D -->|"si"| E["seed.sh machine<br/>Docker, observer, llaves"]
  E --> F["seed.sh project<br/>contrato, CLAUDE.md, hooks, skills, OpenSpec"]
  F --> G["Corpus piloto<br/>skill project-memory-bootstrap"]
  G --> H["memctl sync --apply<br/>indexa, gasta tokens, pide aprobación"]
  H --> I["seed.sh panel y verify"]
```

## 3. Ciclo de una sesión
```mermaid
sequenceDiagram
  participant U as Tú
  participant CC as Claude Code
  participant H as Hooks
  participant M as Memoria Cognee
  U->>CC: abres sesión en el repo
  CC->>H: SessionStart
  H->>H: briefing (Markdown + Git) y registra cambios de versiones
  H-->>CC: briefing inyectado, sin consultar Cognee
  H->>H: lanza auditoría OSV en segundo plano si pasaron 24 h
  U->>CC: pides algo ambiguo
  CC->>M: recall CHUNKS top_k 3, antes de decidir o preguntar
  M-->>CC: fragmentos con ruta y estado
  CC->>CC: verifica frescura con memory_stale, sin tokens
  U->>CC: cierras o compactas
  CC->>H: SessionEnd o PreCompact
  H->>H: checkpoint auto-rama.md
```

## 4. Qué lleva el briefing
```mermaid
flowchart LR
  P["project.md<br/>objetivo"] --> B["Briefing<br/>máx. 6000 caracteres"]
  D["decisions/<br/>vigentes"] --> B
  R["business/<br/>reglas"] --> B
  T["pendientes abiertos"] --> B
  DP["Despliegues<br/>por entorno y rama"] --> B
  S["Seguridad<br/>vulnerabilidades abiertas"] --> B
  O["OpenSpec<br/>cambios activos"] --> B
  C["Checkpoint de la<br/>rama actual"] --> B
  HR["Último handoff real"] --> B
  ST["Notas obsoletas"] --> B
```
El tope recorta el cuerpo, nunca el pie con las instrucciones de uso.

## 5. Auditoría de seguridad automática
```mermaid
flowchart TD
  S["SessionStart"] --> SN["memory_deps snapshot<br/>lee lockfiles"]
  SN --> CH{"Cambió alguna versión?"}
  CH -->|"sí"| LOG["Registra en dependencies.json<br/>motivo: security si el commit cita CVE o GHSA, si no upgrade"]
  CH -->|"no"| AGE
  LOG --> AGE{"Última auditoría con más de 24 h?"}
  AGE -->|"no"| SHOW
  AGE -->|"sí"| BG["memory_audit run<br/>proceso desacoplado, no bloquea"]
  BG --> OSV["api.osv.dev<br/>solo nombre y versión"]
  OSV --> RES["Resultado fuera del repo"]
  RES --> DOC["docs/agent-memory/security/dependencias.md<br/>casillas pendientes"]
  RES --> SHOW["Briefing: abiertas, altas y críticas,<br/>versión que corrige"]
  OSV -.->|"sin red"| FAIL["Falla en silencio y lo anota"]
```

## 6. Despliegues y ramas
```mermaid
flowchart TD
  X["Despliegas a un entorno"] --> V{"Salud verificada?"}
  V -->|"no"| NO["No se registra nada"]
  V -->|"sí"| REC["memory_deploy record<br/>entorno, commit, nota"]
  REC --> ST["En el próximo briefing"]
  ST --> Q1["Commits de la rama principal<br/>sin desplegar"]
  ST --> Q2{"Rama actual"}
  Q2 -->|"integrada en la principal"| Q3["Desplegada si es ancestro<br/>de lo desplegado"]
  Q2 -->|"no integrada"| Q4["Marcada NO desplegada<br/>con sus commits propios"]
```
En proyectos de datos «desplegado» significa que el job/release de producción terminó bien sobre ese commit.

## 7. OpenSpec dirige los cambios
```mermaid
flowchart LR
  I["Idea o petición"] --> M{"Ambigua?"}
  M -->|"sí"| REC["Consulta memoria<br/>y specs vigentes"]
  M -->|"no"| P
  REC --> P["/opsx:propose<br/>proposal, specs, design, tasks"]
  P --> RV["Revisión del usuario"]
  RV --> AP["/opsx:apply<br/>implementa las tareas"]
  AP --> AR["/opsx:archive<br/>los specs vigentes se actualizan"]
  AR --> SY["memctl sync<br/>los specs entran a la memoria"]
```
Excepciones sin cambio: erratas, formato, comentarios y hotfix urgente (se documenta después con un cambio).

## 8. Detección del tipo de proyecto
```mermaid
flowchart TD
  R["Repositorio"] --> E["Busca evidencias<br/>dbt_project.yml, workflow_settings.yaml, .sqlx,<br/>Terraform google_bigquery, package.json, manage.py..."]
  E --> L{"Capas detectadas"}
  L -->|"una combinación clara"| OK["dbt+snowflake, dbt+bigquery,<br/>dataform+bigquery, bigquery, webapp..."]
  L -->|"dbt sin adaptador, dos warehouses,<br/>repo vacío"| ASK["Salida 2: el agente pregunta<br/>con las opciones"]
  ASK --> FORCE["--profile capas"]
  OK --> APPLY["Reglas en CLAUDE.md y exclusiones de indexación"]
  FORCE --> APPLY
```
Para los diagramas de arquitectura detallados (escritura, lectura, continuidad, historia) ver [`diagrams.md`](diagrams.md).
