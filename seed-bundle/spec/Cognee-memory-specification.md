# Project memory with Cognee

Implementation specification · October 22, 2026 · Updated October 26, 2026 after the pilot installation and first operating decisions · Design v1.6 · English edition

Status: **installed and validated as a pilot** on the pilot project on October 26, 2026 (Apple M1, 32 GB, macOS 26.6.2, Docker Desktop). The stack lives in `<KIT>/`; its `config/versions.lock` pins what was tested. Sections marked **[Verified]** record observed behavior; unmarked values remain initial targets, not guaranteed performance or necessarily native Cognee settings. Section 18 lists every gotcha found during installation; sections 19–20.1 record the token strategy, session continuity and the cost of keeping session history; **section 21 is a step-by-step replication playbook** (sections 23–26, v1.6, add the local data flow, the install-time language choice, the seed bundle for agents, and the Management Memory dashboard) and the folder `reference-implementation/` holds the tested code, templates and installer (no secrets). Where an earlier section disagrees with 20.1 or 21, the later section wins.

The [README](README.md) defines paths, responsibilities, six skill contracts, scripts, implementation order, and operations. The [visual map](Cognee-memory-map.png) summarizes the architecture. Skills are specified, not installed; scripts and Compose remain to be implemented. The [study guide](Cognee-technical-study-guide.docx) explains the technical concepts.

## 1. Intended outcome

Claude Code should resume a project without repeated architecture explanations, retrieve previous implementations, recognize current decisions, and preserve verifiable pending work. Memory is agent-independent: Codex will later access the same knowledge through MCP.

“Semantic searches over Markdown from previous implementations” describes the first use case exactly. Markdown holds reviewable knowledge; Cognee builds a retrievable representation; Claude receives only task-relevant background. This neither retrains the model nor guarantees complete recall.

Example: for a dbt incremental-model change, retrieve the previous implementation, watermark rationale, tests, and known limitations with file/commit links.

## 2. Architecture decisions

| Component | Proposed decision | Reason |
|---|---|---|
| Computer | Apple M1 Mac; RAM unconfirmed | Keep local workload small |
| Initial agent | Claude Code with existing subscription | Use current working environment |
| Memory | Locally self-hosted Cognee | Shared persistence/retrieval |
| Integration | **[Verified]** Plugin `cognee-memory` 1.7.4 as an HTTP client of the Docker server (`COGNEE_BACKEND=cloud`, `COGNEE_MANAGED_ENDPOINT=true`); MCP for explicit recall | Initial automation and portability |
| Canonical documentation | Markdown in each repository | Review, Git history, reconstruction |
| Semantic processing | Integration observer mode, subject to testing | Use Claude Code without a large local LLM |
| Embeddings | **[Verified]** `jinaai/jina-embeddings-v2-base-es` via fastembed (768 dims, ES/EN, 8k context) | Avoid an embedding API; a 128-token multilingual MiniLM would truncate most chunks |
| Storage | PostgreSQL + pgvector; embedded Ladybug graph | Consolidate metadata/vectors while retaining native graph |
| Execution | **[Verified]** Docker backend, Mac agents; the Mac-side observer is reachable from the container (§16) | Reproducible operation |
| Deployment | Single user, loopback access | No public server required |

Cognee documents hybrid graph/vector architecture and embedded storage options [2]. The initial embedded-storage proposal is superseded here by PostgreSQL + pgvector and Ladybug. The plugin documents an observer invoking Claude Code under subscription limits, with Haiku by default and local fastembed embeddings. Graph processing can consume substantial tokens [1]. This is an integration capability, not an Anthropic contractual guarantee; verify compatibility and current conditions at installation.

## 3. Information flow

1. Claude works on a task and queries project background.
2. It reads the current repository to verify remembered information still applies.
3. At a meaningful work boundary it writes/updates Markdown.
4. The user can review Markdown like a code change.
5. A synchronizer identifies new, changed, superseded, deleted documents.
6. Cognee processes pending changes and updates derived knowledge.
7. Another session/agent retrieves relevant snippets with source references.

Curated document memory and session capture are separate paths. Prioritize the former in the pilot. Do not assume plugin activation automatically ingests a whole folder or implements our incremental synchronizer.

## 4. Sources and organization

Proposed per-repository layout:

```text
docs/agent-memory/
  project.md
  architecture.md
  business/
  decisions/
  implementations/
  runbooks/
  handoffs/
```

| File/directory | Content |
|---|---|
| project.md | Objective, components, vocabulary, links |
| architecture.md | Current design and constraints |
| business/ | Glossary, metric definitions, rules, owners, effective dates |
| decisions/ | Decisions, alternatives, rationale |
| implementations/ | Changes, validation, limitations |
| runbooks/ | Reproducible procedures |
| handoffs/ | Temporary task state and next steps |

Do not initially index full logs/conversations, production data, downloaded dependencies, binaries, or all code as semantic text. Evaluate optional code-graph usefulness separately for Python, SQL, YAML, dbt.

Document business context explicitly: definitions, exclusions, grain, time windows, approved source, owner. Separate it from temporary task state and link it to models/implementations through verifiable metadata. The README provides an example and skill responsibilities. Neither meeting/chat ingestion nor approval of captured claims is automatic.

## 5. Memory document schema

Proposed template; these fields belong to our document contract. Cognee is not assumed to filter them automatically.

```markdown
---
id: impl-orders-watermark-001
project_id: client-project
type: implementation
status: verified
created_at: 2026-10-22
updated_at: 2026-10-22
source_commit: <actual-commit>
source_paths:
  - models/orders.sql
supersedes: []
tags: [dbt, incremental, watermark]
---
# Orders incremental loading
## Problem and scope
## Implementation
## Decision and rationale
## Alternatives and failed attempts
## Validation evidence
## Limitations
## Pending work
```

Statuses: `draft`, `verified`, `superseded`, `archived`. Separate document status from current applicability: a verified implementation may have been replaced. A hypothesis or Claude answer is not evidence. Store tool outcomes and validation as observed facts with their scope intact.

## 6. Isolation and freshness

Confirmed PostgreSQL decision: one `agents_memory` database; `pgvector` provider and supported `pgvector_shared` handler manage a `ds_<dataset_id>` schema per vector dataset. Do not implement prefixed/suffixed per-project tables or rename managed schemas to force `agents_`. Our Docker resources retain `agents_`; internal objects retain native conventions. Relational metadata and session cache are not assumed duplicated in each schema. Ladybug separates graph data by dataset. Verify isolation mode, permissions, creation/querying/deletion with two projects. Keep project/dataset/schema mappings in the adapter registry.

**[Verified] Prerequisites and behavior.** `pgvector_shared` requires `ENABLE_BACKEND_ACCESS_CONTROL=true`, which turns on users and authentication (`REQUIRE_AUTHENTICATION=true`, a default user with a password, JWT secrets, API keys). With access control the vector engine also needs its own `VECTOR_DB_HOST/PORT/NAME/USERNAME/PASSWORD` even though they equal the relational `DB_*`; without them `/health` returns 503 (`Missing required pgvector credentials`). Observed with two datasets: one schema `ds_<dataset_id>` per dataset (6 tables each) in `agents_memory`, and one Ladybug file `<user_id>/<dataset_id>.lbug` per dataset; queries returned no cross-dataset content in either direction; `forget` on one dataset removed its schema and graph file and left the other intact. Single-user isolation is not an access-control boundary between people (the last bullet below still applies).

- Stable memory namespace per client/project; checkout path is not business identity.
- Separate durable project memory from branch/task handoffs.
- Retrieve only active-project knowledge by default. Global personal memory is opt-in and contains general preferences only.
- Never share client-specific memories across clients.
- Use commits/paths to detect staleness and compare relevant changes against HEAD.
- Preserve decision history; exclude superseded decisions from ordinary retrieval or label them clearly.
- Validate actual dataset/search isolation in the installed release. Datasets do not replace access control for additional users.

## 7. Hooks: intended behavior

Claude Code events/triggers are documented in [3]. The following actions are our specifications; map them against the installed plugin first to avoid duplication.

| Event | Proposed action | Cost control |
|---|---|---|
| SessionStart | Resolve project, check memory, load short summary | Cache summary; no graph rebuild |
| UserPromptSubmit | Retrieve task-related background | Skip greetings/repetition; reuse context |
| PreCompact | Checkpoint new decisions/pending work | Changes since last checkpoint only |
| Stop | Detect work ready to document | No write/process on every response |
| SessionEnd | Flush pending-change queue | Never the sole safeguard |
| PostToolUse | Flag relevant changes for documentation | Filter tools/paths; no full dumps |

**[Verified]** With `COGNEE_CAPTURE=false` no session content reached the server (the sessions dataset stayed at 0 items and `/api/v1/sessions` listed only the MCP's own default session); the plugin did create empty datasets (`<dataset>_sessions`, and a `codebase-*` one even with auto-index off). With a loopback `COGNEE_BASE_URL` the plugin treats the server as "local" and its default `COGNEE_CODE_AUTOINDEX=auto` created a `codebase-*` dataset for the repository on the first session; set `COGNEE_CODE_AUTOINDEX=off` (and `COGNEE_FILE_CONTEXT=false`) to honor "do not index all code initially". When the backend is down the hooks print connection warnings and reconnect later without blocking the session. **[Verified Oct 26]** `claude plugin disable cognee-memory@cognee --scope local` stops capture: counting `claude_*` sessions in `/api/v1/sessions`, a control run with the plugin on added 1 and a run with it off added 0. A real `/compact` (print mode: `claude -p "/compact" --resume <id>`) reduced the context from 46,349 to 12,288 tokens and all five planted facts were recovered afterwards (small test; long sessions untested).

Initial phase: explicit retrieval and Markdown saving. *(Superseded Oct 26, 2026: session capture was switched ON with cost caps — see 20.1; review after one week.)* Add filtered automatic capture after measuring usefulness/consumption. The plugin supports `COGNEE_CAPTURE=false` to pause capture while retaining retrieval/explicit saving [1]. Verify what processing continues under that setting.

Saving a checkpoint must not make the model continue indefinitely. If a hook fails, record the failure and continue normal work; retain the queue for deduplicated retries.

## 8. Proposed M1 and subscription optimization

| Design parameter | Initial proposal |
|---|---|
| Pilot corpus | 10–20 representative Markdown documents |
| Processing concurrency | One semantic job at a time |
| Suggested document size | 500–1,500 words; split by topic when appropriate |
| Retrieval results | Up to five snippets per initial query |
| Memory context budget | 1,000–2,000 tokens; expand only when useful |
| Retrieval cache | Up to ten minutes; invalidate on memory/project changes |
| Processing | Small batches, changed content only |
| Additional enrichment | Disabled unless improvement demonstrated |
| Full-trace capture | Pilot started OFF; **ON with caps since Oct 26** (20.1); `COGNEE_CAPTURE=false` is the only documented switch |

Use native settings where available; other controls require a small adapter. The plugin is not promised to expose them all.

**[Verified] Measured on the pilot (15 Markdown documents, ~2,600 words, 30 chunks).** First ingestion: 6 minutes, 74 observer completions on `haiku`, 0 failures, ~307,000 total tokens (cache reads included; the observer log does not split categories, so categories are *unknown*, not zero). A one-document update costs one `cognify` (~5–17 s). Unchanged re-sync: 0.28 s, zero calls. Warm retrieval: p50 0.12 s, p95 0.18 s. Docker Desktop VM: 8 GB / 8 CPUs was ample.

Monthly cost cannot be determined without volume, calls, Claude plan measurements. Subscription limits apply; it is not an unlimited API. Record observer usage and compare against no-memory sessions. Do not keep a large local LLM on the M1 in the pilot.

Test observer-mode local embeddings with Spanish questions and English documentation. If bilingual retrieval fails, evaluate a small multilingual embedder. Changing models requires regenerating a compatible index; never mix vectors from different models.

## 9. Incremental synchronization

Design a local registry with `project_id`, `document_id`, relative path, content hash, commit, schema version, embedder version, status, last error. No secrets.

Intended algorithm:

1. Enumerate allowed paths and compare hashes.
2. Enqueue new/changed documents; skip unchanged ones.
3. Process idempotently by project/document/hash.
4. Verify new-version retrieval before marking success.
5. Retire/invalidate the old version and derivatives through available APIs.
6. Detect deletions and superseded documents.
7. Retry errors with bounds and increasing delay.

**[Verified] semantics (Cognee 1.6.5).** `add` is idempotent by content (same text → same `data_id`). There is no in-place update: replace = `DELETE /api/v1/datasets/{id}/data/{data_id}` + `add` of the new text + `cognify`; after that the old text is no longer retrievable and `cognify` processes only the new data. Deleting a registry entry = the same `DELETE`. Search chunks carry `document_id` equal to the `data_id`, which is the reliable way to attribute a hit to a source (later chunks of a document do not repeat the header line). Implemented in `scripts/sync_markdown.py` (registry in `~/.local/share/agents_memory_system/registry.json`, atomic writes, file lock, states `submitted → indexed|unverified|error`).

Verify Cognee update/delete semantics before implementing. If precise updates are unreliable, rebuild only the pilot dataset from Markdown. Never silently accumulate contradictory versions.

## 10. Connect, disconnect, pause

Define three distinct operations:

- Pause capture: query background without recording the session.
- Disconnect an agent: disable its integration and hooks; preserve documents/storage.
- Stop local memory: stop services/sync jobs; basic agent work must remain possible.

Disabling MCP alone does not prove hooks stopped capturing. Operations must verify both paths and that no new records appear after disconnection.

Codex uses the same project/dataset/sources. Claude hooks do not transfer automatically: Codex needs its own read/write policy. Test cross-agent reads before enabling concurrent writes.

## 11. Privacy and backup

Local memory is not fully local processing: text sent to Claude is processed outside the Mac. Limit documents/snippets according to client rules.

Exclude `.env`, keys, tokens, credentials, third-party personal data, production records. Plugin filtering helps but does not replace a content allowlist.

Back up Markdown in the corresponding private repository. Back up configuration without secrets, sync registry, and Cognee data using backend-supported consistent procedures; do not copy live databases without validating consistency. Knowledge should be reconstructible from documents even if reconstruction consumes processing again.

## 12. Implementation stages

| Stage | Work | Exit condition |
|---|---|---|
| 0. Inventory | RAM, macOS, disk, Claude/Python versions, plan | Requirements/compatibility verified |
| 1. Local pilot | Install pinned versions, verify observer/embeddings | Simple memory saved/retrieved |
| 2. Corpus | Markdown and document template | 10–20 sourced documents |
| 3. Retrieval | Ingest and evaluate real questions | Correct sources, isolated projects |
| 4. Incremental sync | Hashes, queue, replacements, deletions | Reprocessing without duplicates |
| 5. Automation | Enable useful hooks progressively | Useful capture without uncontrolled growth |
| 6. Portability | Add Codex to shared knowledge | Verified cross-agent retrieval |
| 7. Operations | Pause, disconnect, restore, measure | Reproducible procedures |

Before installation pin plugin release/commit and compatible Cognee version; avoid automatic updates during pilot. Inventory Claude native memory to prevent contradictory rules or unexpected configuration changes.

## 13. Evaluation and acceptance criteria

Build 20 questions with expected source documents: decisions, implementations, pending work, relationships, unanswerable questions. Include Spanish and English.

Initial targets, subject to measurement:

- Relevant source in first five results for at least 17/20 answerable questions.
- Zero crossover between two isolation-test projects.
- Show date/source and identify superseded memories.
- Do not invent answers when documentation is insufficient.
- Unchanged synchronization causes no new semantic processing.
- Updating a document changes the answer; deletion removes retrievable content.
- Resume a task in a new session and then another agent.
- Record latency, calls, usage; separate ingestion/query costs.
- Indicative warm-retrieval p95 below three seconds excluding agent generation; revise against evidence.
- Cognee failure does not block normal work; full disconnection neither captures nor queries.

### Pilot results (October 26, 2026, the pilot project, 15 documents) [Verified]

| Criterion | Result |
|---|---|
| Relevant source in top 5 | 18/18 answerable questions (ES 14/14, EN 4/4); 2 unanswerable reported only — abstaining is an agent decision |
| Warm retrieval | p50 0.12 s, p95 0.15–0.18 s (target < 3 s) |
| Project isolation | 0 crossover (2 test datasets, both directions); selective deletion |
| Unchanged sync | 0.28 s, no semantic processing |
| Update / delete | Old version stops being retrievable; deleted content gone |
| Persistence | Survives `stop`/`up` |
| Backup / restore | 30 chunks live = 30 restored; 2 schemas, 2 graph files |
| Cognee down | Normal Claude session (4.5 s) |
| Disconnect | **Verified Oct 26**: sessions +1 with the plugin on, +0 with it off (the first check was invalid) |
| `/compact` | **Verified Oct 26** (small test): 46,349 → 12,288 tokens, 5/5 facts recovered |
| End-to-end skill | `project-memory-recall` answered correctly with sources; its first run hit a 404 (wrong dataset name) and fell back to Markdown as designed |
| A/B (one question, one repeat, **preliminary**) | B (Cognee + verification against code) cost **3.0×** A (read the same Markdown directly): ≈$0.0118 vs $0.0040 per run |

Interpretation: with 15 small documents direct Markdown reading is cheaper; the A/B sample is far too small to conclude, B also performed the code verification the skill requires and A did not, and the ingestion cost is not yet amortized. This is exactly the case the next paragraph anticipates. Not yet measured: the five-fact `/compact` test, cross-session and cross-agent resumption, a corpus large enough that reading everything is no longer viable.

Compare against Claude directly reading the same Markdown. If Cognee does not improve retrieval or measurable savings, adjust before expanding the corpus.

## 14. Future implementation deliverables

Versioned configuration without secrets; memory template; pilot corpus; Claude integration; incremental adapter if needed; reproducible evaluation; activation/pause/disconnection/restore runbook; subsequent Codex integration; version/usage ledger.

Before final parameter selection confirm M1 RAM, macOS/Claude versions, subscription plan/limits, repository size/languages, client data restrictions. These do not prevent conceptual design approval.

## 15. Conversation compaction: analysis and contract

Compaction reduces Claude's active context by replacing part of the history with a smaller representation. It does not store full history in Cognee or update Markdown. Repository files are not deleted. Details absent from the summary can be lost; external memory must still be retrieved afterward.

The plugin README declares a memory anchor in `PreCompact` [1]. This does not prove every preceding detail is persisted, processed, reinjected. Inspect the pinned release's script, inputs, outputs. Do not assume PreCompact receives the entire conversation or can ask the main Claude model for a synchronous summary then.

Proposed design:

1. Maintain incremental handoff during work before reaching context limits.
2. At PreCompact, save a small checkpoint from existing state and enqueue any delta; no full graph rebuild or blocking long calls.
3. Write atomically to disk first, then send to Cognee. Distinguish local checkpoint, accepted submission, completed indexing.
4. Restore at the next supported opportunity: PostCompact, SessionStart with compaction reason, or next prompt. Verify actual behavior and prevent triple injection.
5. Load recent local state even if Cognee processing is unfinished; local Markdown is fallback.

Checkpoint contents: project, branch/commit, objective, constraints, new decisions/sources, changed files, tests/results, failed attempts, pending work, next action. Mark unvalidated work. Do not store private internal model reasoning or infer it from transcripts.

Required test: establish five identifiable facts, force `/compact`, verify checkpoint and recovery of constraints, decision, test, pending item, source. Repeat with Cognee unavailable and a new session. Record exactly what returns; do not claim complete preservation.

## 16. Docker on Mac M1: options and decision

Cognee has a documented Docker/MCP route [4]. All local processes can in principle be containerized, but Claude still calls Anthropic remotely; Docker does not make inference local.

| Variant | Benefit | Cost/limitation | Decision |
|---|---|---|---|
| Native Claude/plugin/Cognee | Fewer components for subscription-observer testing | Local Python environment | Lowest-complexity pilot |
| Claude/hooks on Mac; Cognee in Docker | Isolated backend, volumes, reproducible startup | Host observer needs explicit connectivity/adaptation | Deployment target |
| Claude/hooks/observer/Cognee in containers | Encapsulated local processes | Login, session persistence, Linux paths/tools | Later experiment |

For Docker endpoints the plugin documents `COGNEE_MANAGED_ENDPOINT=true` to prevent backend failure from starting a local fallback server [1]. Configure container provider/embedder separately; managed mode does not inherit the host observer.

**[Verified] Observer from Docker.** The plugin's observer (`claude-observer.py`) binds to `127.0.0.1:8017` (hard-coded), requires `Authorization: Bearer <token>` (token in `~/.cognee-plugin/observer/token`; that directory also holds the secret and must never be mounted) and refuses requests with an `Origin` header. On Docker Desktop for Mac a container **can** reach that loopback-only listener at `http://host.docker.internal:8017/v1`. The Cognee API runs with `LLM_PROVIDER=custom`, `LLM_MODEL=openai/claude-observer`, `LLM_ENDPOINT` = that URL, `LLM_API_KEY` = the token and `LLM_INSTRUCTOR_MODE=json_schema_mode`; 74 completions ran this way with 0 failures. Caveats: tested only on Docker Desktop (Colima/OrbStack untested); the observer is a Mac process: start it with `memctl.sh up` or install the LaunchAgent (`scripts/observer_launchagent.sh install`, verified: auth ok under launchd, restart after `kill`, reachable from the container); started without `--cognee-url` it never self-retires. A containerized observer or an authenticated bridge was therefore not needed.

Future Compose requirements:

- `agents_` prefix for our services/volumes: `agents_postgres`, `agents_cognee_api`, `agents_cognee_mcp`, `agents_otel_collector`, `agents_analytics`; volumes `agents_pgdata`, `agents_graph_data`, `agents_model_cache`, `agents_telemetry_raw`, `agents_analytics_data`. Update internal DNS/references; preserve official skill/package names. Compose prefixes physical names with project name.
- One `agents_memory_system` project with Compose-managed exclusive bridge `agents_memory_net` and service DNS. No shared external network, static IPs, host networking. API, MCP, Postgres, collector, analytics job belong to this stack; Ladybug/embeddings run inside Cognee, DuckDB inside analytics.
- Outbound Internet for Anthropic/downloads; exclusive network does not mean `internal: true` or offline. Claude/hooks remain on Mac. Resolve observer connectivity without LAN exposure; any containerized helper joins the same Compose after authentication validation.
- Candidate Mac ports: MCP 45873, API 45874, OTLP/gRPC 45875. Bind to `127.0.0.1`; check availability; reassign consistently on conflict. Internal ports follow images. PostgreSQL has no host port by default.
- Native ARM64 image or tested Apple Silicon build; pin tag/digest. Do not assume every tag publishes ARM64.
- Docker Cognee, PostgreSQL/pgvector, OTel collector. Embedded Ladybug. Postgres session cache only after release validation. No production reliance on demo Postgres graph backend.
- Persistent volumes for data, model cache, queue. Canonical documents remain in repositories.
- Mount only necessary directories, read-only for ingestion where possible.
- Loopback endpoints and API-appropriate authentication.
- Healthchecks, RAM-informed resource limits, graceful shutdown.
- No Docker-socket or whole-home mount.
- `docker compose stop` pauses; `down` normally removes containers/networks while retaining named volumes. Never use `down -v` to pause.
- Back up and test volume restoration before upgrades.

Current choice: Docker infrastructure with PostgreSQL/pgvector, Cognee/Ladybug, collector; agents on Mac. Validate observer with a small corpus, then its Docker-backend connection before scaling ingestion. Native pilot is an explicit validation/fallback stage if connectivity is blocked, not a permanent parallel installation. Never run two backends writing the same database files.

## 17. Measurement, official skills, sources, verification limits

### Net-savings measurement per project

The README defines the framework: Claude OTel + observer logs + script events → local collector → normalizer/ledger → DuckDB queries and A/B report. Langfuse is optional later, subject to resources/signal adaptation, not required for pilot.

Collector Contrib runs in Docker with host OTLP/gRPC at `127.0.0.1:45875`; file exporter writes rotated persistent OTLP JSON. On-demand DuckDB requires no server. Parse OTLP before building analytical tables. Telemetry and business memory remain separate. Initial retention: 14 raw days / 90 aggregate days. The README specifies operations, coverage gaps, privacy, tests; no guaranteed outage delivery or installed dashboard.

Normalization/reports run in `agents_analytics` on the same Compose network with user-accessible mounted outputs. Collector does not replace analytical persistence or calculate savings; comparator accounts for agent + observer + maintenance without duplication.

Attribute by project/task/run and actor/phase. Separate input/cache/output, ingestion, maintenance, evaluation; deduplicate OTel/log overlap and do not count retrieved context twice. Show instrumentation coverage and unknown counts explicitly.

Compare equivalent tasks with identical sources/model/commit; baseline may directly read Markdown. Isolate each round's corpus/results. Report success/quality with consumption, amortize ingestion once, distinguish API-equivalent cost from subscription spending/limits. Framework is specified, not deployed.

### Official skills and installation order

Use the supplied Agent Skills page to incorporate Cognee-maintained skills. Pin instructions and read `cognee-install`; use `cognee-integrations` to preserve Claude observer/local embeddings decisions. Add server, ingestion, recall, improve-sessions, performance, docker, forget, cli according to task. README details selection, paths, validation.

Official skills explain API/installation; six custom skills define our per-project procedures; plugin supplies hooks. These are not interchangeable. Do not install two runtimes into one environment, execute global resets from inline examples, or switch to paid-provider defaults.

First test: fresh dataset with `remember`/`recall`, cross-session persistence, actual provider verified. Inspect query feedback and additional `remember` processing before changing optimization flags. Keep indexing/retrieval verifiable.

### Sources

[1] Official Cognee–Claude Code integration: https://github.com/topoteretes/cognee-integrations/blob/main/integrations/claude-code/README.md — consulted October 22, 2026. Plugin/observer capabilities; reconfirm versions/settings at installation.

[2] Cognee architecture: https://www.cognee.ai/how-cognee-builds-ai-memory — hybrid architecture and embedded storage.

[3] Claude Code hooks: https://code.claude.com/docs/en/hooks — events and execution lifecycle.

[4] Cognee MCP server: https://github.com/topoteretes/cognee/blob/main/cognee-mcp/README.md — MCP-client access.

[5] Official installation skill: https://github.com/topoteretes/cognee/blob/main/.agents/skills/cognee-install/SKILL.md . Catalog: https://github.com/topoteretes/cognee/tree/main/.agents/skills . Supplied Agent Skills page in `Pasted text.txt`; documentation index: https://docs.cognee.ai/llms.txt .

[6] Dataset handlers: https://docs.cognee.ai/core-concepts/multi-user-mode/dataset-database-handlers/dataset-database-handlers-how-to-use-them .

Architecture, budgets, document schema, queue, acceptance criteria are implementation proposals, not already configured or guaranteed product capabilities.

## 18. Installation lessons (read before installing again)

Observed on October 26, 2026 with Cognee 1.6.5, plugin 1.7.4, Docker Desktop 27.5.1 on an M1. In the order they appeared:

1. **Access control is mandatory** for `pgvector_shared` (§6); it brings authentication, a default user and API keys.
2. **User email is validated:** reserved domains such as `.local` crash startup. Use a real-looking domain.
3. **Named volumes are created root-owned.** The non-root `cognee` user could not write the fastembed cache; fix with a thin image (`FROM cognee/cognee:<pin>`; `mkdir /models; chown`) so Docker copies ownership into the new volume.
4. **Give the vector engine explicit `VECTOR_DB_*` credentials** under access control, or `/health` stays 503.
5. **MCP → API auth:** self-hosted API keys need `COGNEE_API_AUTH_SCHEME=x-api-key`; the MCP default is `Bearer` and gets 401. Create the key with `POST /api/v1/auth/api-keys`.
6. **OTel Collector Contrib is distroless** (no shell, uid 10001): its output volume needs a one-shot init container that `chown`s it. Raw files are mode 0600, so the analytics job reads them as root, read-only.
7. **MCP `recall` takes `datasets` as a string**, not a list; an unknown name is a 404 `Dataset(s) not found`. Omitting `search_type` makes the server synthesize an answer (more LLM work); `CHUNKS` is plain retrieval.
8. **Plugin defaults to review:** `COGNEE_CODE_AUTOINDEX=auto` indexes the repo when the URL is loopback; set it `off`. With capture off no session content is stored (see section 7), but empty datasets are still created.
9. **Observer reachability:** works through `host.docker.internal` on Docker Desktop (§16).
10. **Telemetry accounting:** use `claude_code.api_request` log events as the authoritative per-call record. Delta metrics under-count short sessions by 2–37 % (the last export window is not flushed); token categories reconcile exactly when the session lives long enough. The observer log has totals only.
11. **Plugin install scope:** `claude plugin install … --scope local` keeps it out of the repository; settings live in `~/.cognee/.env` (global, mode 600), which is shared with the Codex plugin.
12. **Shell:** in zsh a variable holding a compound command is not word-split; wrap Compose in a script (`dc.sh`).
13. **Operations that proved safe:** `docker compose stop`/`up` (data persists), backing up with the API stopped (`pg_dump -Fc` + tar of the graph volume) and restoring into disposable containers.
14. **Cost reality:** for a small, well-organized corpus, direct Markdown reading beat Cognee on tokens in the first A/B (§13). The expected benefits are scale, cross-session/agent continuity and graph relations; measure them before expanding.

### Still open after the pilot
PreCompact/`/compact` five-fact test; custom hook handlers; skills `bootstrap`, `maintain`, `evaluate`; Codex; ES/EN embedder comparison; an A/B with enough tasks to amortize ingestion; LaunchAgent for the observer; behavior on Colima/OrbStack.

## 19. Token strategy (researched and measured, October 26, 2026)

Sources: Cognee's technical note on persistent-memory token cost, its `cognee-performance` skill, the search-type docs, and the plugin README; plus pilot measurements. Full version: `agents_memory_system/docs/token-strategy.md`.

- **Ingestion dominates.** Each chunk costs about two LLM calls (summary ≈ 27 %, graph extraction ≈ 73 % of tokens). Cognee reports ≈ 23–25× the corpus tokens to ingest and ≈ 1–2 k retrieved tokens per query, with break-even against full-context at ≈ 23–26 queries for 16–200 k-token corpora. **[Verified]** here: ≈ 307 k tokens for a 4 k-token corpus (≈ 75×) because every `claude -p` observer call carries ≈ 23 k tokens of cached Claude Code prompt; break-even against reading the corpus directly would need > 100 queries.
- **`chunkSize` is not a lever for small documents [Verified]:** 2000 vs 4000 produced the same 3 chunks and 6–7 calls; cost follows paragraph/section count. `extractor="gliner"` (no-LLM graph) exists only in the SDK `remember()`, not in the 1.6.5 REST API.
- **Query cost by search type:** `CHUNKS`/`CHUNKS_LEXICAL`/`SUMMARIES`/`CODE` use no LLM; completion types ≥ 1 call; `GRAPH_COMPLETION_COT`, `_DECOMPOSITION`, `_CONTEXT_EXTENSION`, `TEMPORAL` several. MCP `recall` without `search_type` synthesizes an answer (LLM): always pass `CHUNKS`.
- **Settings applied:** server `AUTO_FEEDBACK=false`, `IMPROVE_AUTO_ENABLED=false` (keep `CACHING=true`); plugin `COGNEE_AUTO_IMPROVE_EVERY=0`, `COGNEE_INJECT_MAX_CHARS=3000`, `COGNEE_RECALL_PASSAGE_CHARS=600`, capture and code autoindex off. The plugin's per-prompt recall only searches the active session dataset (empty in the pilot), so it injects almost nothing.
- **Operating rules:** query only for history that `CLAUDE.md` lacks, once per task, `top_k` 3–5; decide freshness with `git diff <source_commit>..HEAD -- <source_paths>` (`scripts/memory_stale.py`, zero tokens) instead of re-reading code; sync once per task/milestone; do not index content already in `CLAUDE.md`; use Cognee when the corpus no longer fits comfortably in context, spans several projects/agents, or needs cross-document relations. Below roughly 30 k tokens, reading the Markdown directly is cheaper (first A/B: Cognee 3.0×).

## 20. Session continuity without per-prompt queries (implemented Oct 26, 2026)

Goal: open Claude and continue as if the session had never closed, without querying Cognee on every prompt. Design [Verified in a fresh session]: (1) a **deterministic briefing** (`memory_brief.py`, `SessionStart` hook for `startup|resume|clear|compact`, ≈ 1,000 tokens, no LLM, no Cognee) built from `docs/agent-memory/` and Git — objective, current decisions, business rules, open items, latest handoff, stale-note warnings; (2) an **automatic checkpoint** (`memory_checkpoint.py`, `SessionEnd` and `PreCompact`, zero tokens) with branch, uncommitted files, recent commits and the last user requests; (3) a **semantic handoff** written by the `project-memory-handoff` skill when a task ends (asked for by `CLAUDE.md`), and durable knowledge through `project-memory-document` + `sync`; (4) Cognee `recall` only for deeper history. A fresh no-tools session answered decisions, rules and pending migrations in one turn ($0.0075). The briefing only knows what was written down, so the end-of-task handoff is the load-bearing habit. Side effect found: the plugin sets the **global** `autoMemoryEnabled:false` in cloud mode; restore it with `COGNEE_DISABLE_AUTO_MEMORY=false` and turn off `COGNEE_PREFER_MEMORY` (it steers the model to query Cognee constantly). Details: `agents_memory_system/docs/continuity.md`.

### 20.1 History in Cognee: measured cost and corrections (Oct 26, 2026)

Strategy tested: queries are cheap, indexing is expensive → keep a small deterministic briefing, let Cognee keep the *session history*, and query it whenever the briefing does not answer. Findings: (1) per Cognee docs, storing a session turn costs **no LLM call** (cache only) and a `CHUNKS` query costs none either; the session cache **expires after 7 days** unless `SESSION_TTL_SECONDS=0`. (2) **[Verified]** the plugin fires an `improve("final")` when every session ends, promoting it to the graph: 4 trivial sessions cost 21 observer calls (~63 k tokens); with `IMPROVE_DISTILL_MAX_BATCHES_PER_RUN=1` and `IMPROVE_TRACE_WINDOWS_PER_RUN=1` a trivial session cost 3 calls. `COGNEE_AUTO_IMPROVE_EVERY=0` does not stop this final pass and no documented plugin switch does; only `COGNEE_CAPTURE=false` does. (3) **[Verified]** after that promotion a *new* session can recall the fact (`recall` returned it as a graph completion, which itself uses an LLM), so cross-session history works but is paid at session end, not at query time. (4) The plugin's capture worker is a long-lived process that keeps the environment it started with: after editing `~/.cognee/.env` kill `_cloud_worker.py` or captures stay in `~/.cognee-plugin/claude-code/spool/` unsent. (5) Test hygiene: Claude's native auto memory (restored after the plugin disabled it globally) also answers "what do you remember" questions and contaminated the first test; run history tests with `--settings '{"autoMemoryEnabled":false}'`. (6) **Correction:** the earlier "5 → 5 sessions after `plugin disable`" check was invalid (it measured the number of keys of the `/api/v1/sessions` response, not sessions); disconnect behavior was therefore unverified at that point; it was re-verified correctly on Oct 26 (+1 session with the plugin on, +0 off).

## 21. Replication playbook (v1.5)

Goal: reproduce, on another Mac or for another project, the memory stack validated on October 26, 2026. All commands assume the `reference-implementation/` folder of this package copied to `<KIT>/` (call it `$MS`). Values marked *tested* were run; anything else is a design choice you should re-verify.

### 21.1 Prerequisites
| Item | Tested | Notes |
|---|---|---|
| Machine | Apple M1, 32 GB, macOS 26.6.2 | Docker VM of 8 GB / 8 CPUs was ample; smaller untested. Images are published for arm64 and amd64. |
| Docker | Docker Desktop (Engine 27.5.1, Compose 2.32.4) | **Observer reachability from containers was verified only on Docker Desktop for Mac.** Colima/OrbStack/Linux: untested. |
| Claude Code | 2.1.310, logged in with a subscription | The plugin needs ≥ 2.1.287. |
| Others | Python 3 (stdlib only; 3.12), git, curl, `gh` optional | No `uv` and no local Cognee install are needed (Docker backend). |
| Free ports | 45873 (MCP), 45874 (API), 45875 (OTLP), 8017 (observer) | PostgreSQL publishes none. Change consistently in `compose.yaml`, `~/.cognee/.env`, `claude mcp add`, `claude-memory`. |
| Network | Docker Hub, Hugging Face (~640 MB embedder), Anthropic | Docker is not offline: Claude still runs remotely. |

### 21.2 Steps
1. **Inventory** — `sysctl -n hw.memsize; docker info --format '{{.ServerVersion}} {{.NCPU}} {{.MemTotal}}'; lsof -nP -iTCP:45873-45875 -iTCP:8017 -sTCP:LISTEN` (no listeners expected). Start Docker Desktop if the daemon is down.
2. **Copy** `reference-implementation/` to `$MS`. Review `config/versions.lock`; change image tags only deliberately (embedder change ⇒ rebuild every index).
3. **Install the plugin** from the target project directory (scope `local` keeps it out of the repo):
   `claude plugin marketplace add topoteretes/cognee-integrations` then `claude plugin install cognee-memory@cognee --scope local`. Tested: plugin 1.7.4, marketplace commit `e3addddcd0d95bd0b81881953ab851b6eb618051`. **Side effect:** the plugin writes `autoMemoryEnabled:false` into your *global* `~/.claude/settings.json`; undo with `COGNEE_DISABLE_AUTO_MEMORY=false` in `~/.cognee/.env` (step 7).
4. **Observer** — `$MS/scripts/observer.sh start` then `observer.sh probe` (expect `{"auth":"ok"}`). It is a Mac process (127.0.0.1:8017). Either run `memctl.sh up` after every reboot or install the LaunchAgent once: `scripts/observer_launchagent.sh install` (reversible with `uninstall`).
5. **Secrets** — `$MS/scripts/gen_env.sh` writes `deploy/docker/.env` (mode 0600, Git-ignored): Postgres password, API user email/password, JWT secret, and the observer token. The email must not use a reserved TLD such as `.local`.
6. **Stack** — `$MS/scripts/dc.sh up -d agents_postgres agents_cognee_api agents_cognee_mcp agents_otel_collector`; wait until `curl -s 127.0.0.1:45874/health` returns `"status":"ready"` (60–90 s; first run builds the thin image and downloads the embedder). Always use `dc.sh` (zsh does not word-split a variable holding a compound command).
7. **Keys and plugin configuration** — `scripts/mint_mcp_key.py mcp` then `dc.sh up -d --force-recreate agents_cognee_mcp`; `scripts/mint_mcp_key.py plugin` (writes `COGNEE_API_KEY`). Create/extend `~/.cognee/.env` (mode 0600) with the values in 21.4. Restart the plugin worker after any edit: `pkill -f _cloud_worker.py`.
8. **MCP for the project** — from the project directory: `claude mcp add --scope local --transport http agents_cognee http://127.0.0.1:45873/mcp`; `claude mcp list` must show Connected.
9. **Install into the project** — `python3 -I $MS/scripts/install_project.py <repo> --project-id <id> [--lang auto|es|en]` (idempotent; **asks or detects the project language, see 24**): `.agent-memory/project.yaml`, `docs/agent-memory/` skeleton, templates under `.agent-memory/templates/`, the memory section in `CLAUDE.md`, hooks `SessionStart`/`PreCompact`/`SessionEnd` in `.claude/settings.local.json` (local, not versioned), skill symlinks, Git-local excludes.
10. **Write the corpus** — start from `docs/agent-memory/project.md` (the *Objetivo* section feeds the briefing) and the three templates; every claim traceable to a source file; `source_commit` = real `git rev-parse --short HEAD`; `status: verified` only after running the validation. Prefer decisions, implementation evidence, business rules and runbooks **not already in `CLAUDE.md`**.
11. **Index once** — `$MS/scripts/memctl.sh sync <repo>` (plan) then `--apply` (≈ 2 Claude calls per chunk, ≈ 6 min / 74 calls for 15 documents). Expect `indexed` for all; `unverified`/`error` are retried on the next run.
12. **Evaluate** — write 20 questions with expected `doc_id`s in `$MS/evals/cases.<project_id>.jsonl` (format in the reference file; ES/EN, ≥ 2 unanswerable) and run `memctl.sh eval <repo>`.
13. **Accept** — run the checks in 21.5. Commit the project files (`docs/agent-memory/`, `.agent-memory/`, `CLAUDE.md`) through your normal review; infrastructure stays in its own repository.

### 21.3 Server settings (`deploy/docker/compose.yaml`, service `agents_cognee_api`)
| Variable | Value | Why |
|---|---|---|
| `DB_PROVIDER`, `DB_HOST/PORT/NAME/USERNAME/PASSWORD` | `postgres`, `agents_postgres`, `5432`, `agents_memory`, `agents`, secret | One database for relational data and vectors. |
| `VECTOR_DB_PROVIDER` + `VECTOR_DB_HOST/PORT/NAME/USERNAME/PASSWORD` | `pgvector` + same values | Mandatory and explicit under access control (else `/health` 503). |
| `VECTOR_DATASET_DATABASE_HANDLER` | `pgvector_shared` | One `ds_<dataset_id>` schema per dataset. |
| `GRAPH_DATABASE_PROVIDER`, `GRAPH_DATASET_DATABASE_HANDLER` | `ladybug`, `ladybug` | Embedded graph, one `.lbug` file per dataset. |
| `ENABLE_BACKEND_ACCESS_CONTROL`, `REQUIRE_AUTHENTICATION` | `true`, `true` | Required by `pgvector_shared`; brings users and API keys. |
| `DEFAULT_USER_EMAIL/PASSWORD`, `FASTAPI_USERS_*_SECRET` | from `.env` | Never reuse the defaults. |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_ENDPOINT`, `LLM_API_KEY`, `LLM_INSTRUCTOR_MODE` | `custom`, `openai/claude-observer`, `http://host.docker.internal:8017/v1`, observer token, `json_schema_mode` | The Mac observer (`claude -p`) is the LLM; needs `extra_hosts: host.docker.internal:host-gateway`. |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `FASTEMBED_CACHE_PATH` | `fastembed`, `jinaai/jina-embeddings-v2-base-es`, `768`, `/models` | Bilingual, 8k context; `/models` is a named volume owned by `cognee` (thin image). |
| `CACHING`, `SESSION_TTL_SECONDS` | `true`, `0` | Session memory on; do not expire history after 7 days. |
| `AUTO_FEEDBACK`, `IMPROVE_AUTO_ENABLED` | `false`, `false` | Remove per-query and per-write LLM passes. |
| `IMPROVE_DISTILL_MAX_BATCHES_PER_RUN`, `IMPROVE_TRACE_WINDOWS_PER_RUN` | `1`, `1` | Cap the plugin's end-of-session `improve` (5 → 3 calls on a trivial session). |
| `TELEMETRY_DISABLED` | `1` | |
Other services: `agents_postgres` (`pgvector/pgvector:pg17`, no published port), `agents_cognee_mcp` (`COGNEE_API_AUTH_SCHEME=x-api-key`, `API_URL=http://agents_cognee_api:8000`), `agents_telemetry_init` (chown of the collector volume to uid 10001) and `agents_otel_collector` (file exporter, 20 MB rotation, 14 days). Published ports are bound to `127.0.0.1`.

### 21.4 Plugin settings (`~/.cognee/.env`, mode 0600)
| Variable | Value | Why |
|---|---|---|
| `COGNEE_BACKEND` | `cloud` | HTTP-client mode: no local runtime. |
| `COGNEE_BASE_URL`, `COGNEE_MANAGED_ENDPOINT` | `http://127.0.0.1:45874`, `true` | Backend down ⇒ "OFFLINE", never a rogue local server. |
| `COGNEE_API_KEY` | from `mint_mcp_key.py plugin` | Sent as `X-Api-Key`. |
| `COGNEE_CAPTURE` | `true` (pilot decision; `false` to stop all capture) | See 20.1. |
| `COGNEE_PLUGIN_DATASET` | `<project>_sessions` | |
| `COGNEE_CODE_AUTOINDEX`, `COGNEE_FILE_CONTEXT` | `off`, `false` | Do not index code; loopback counts as "local". |
| `COGNEE_AUTO_IMPROVE_EVERY`, `COGNEE_INJECT_MAX_CHARS`, `COGNEE_RECALL_PASSAGE_CHARS` | `0`, `3000`, `600` | Bound per-prompt injection and count-based improves. |
| `COGNEE_DISABLE_AUTO_MEMORY`, `COGNEE_PREFER_MEMORY`, `COGNEE_UPDATE_CHECK` | `false`, `false`, `false` | Restore Claude's native memory; stop steering the model to query Cognee constantly; no update pings. |

### 21.5 Acceptance checks (all *tested*; expected results from the pilot)
| Check | How | Pilot result |
|---|---|---|
| Health | `curl 127.0.0.1:45874/health` | `ready` |
| Observer from a container | `docker run --rm curlimages/curl -H "Authorization: Bearer $(cat ~/.cognee-plugin/observer/token)" http://host.docker.internal:8017/v1/models` | model list |
| Retrieval | `memctl.sh eval <repo>` | 18/18 in top 5; p95 0.15–0.18 s |
| Isolation | two datasets via `cognee_adapter.py`; query each with the other's question; `forget` one | 0 crossover; `ds_*` schema and `.lbug` removed for the forgotten one only |
| Incremental sync | `sync --apply` twice; edit one doc; delete one doc | 0.28 s and 0 calls unchanged; old text gone after replace; content gone after delete |
| Persistence | `memctl.sh stop` then `up` | data intact |
| Backup/restore | `scripts/backup.sh` then `backup.sh restore-test <dir>` | live chunks = restored chunks (30 = 30) |
| Backend down | stop the stack, run `claude -p` in the project | normal answer (4.5 s) |
| Continuity | new session, no tools: ask for decisions, rules, pending items | answered from the briefing (1 turn, $0.0075) |
| History | capture on; fact stated in session A; recall in session B **with `--settings '{"autoMemoryEnabled":false}'`** | recovered only after the session-end improve ran |
| Capture queue | `ls ~/.cognee-plugin/claude-code/spool` after sessions | empty (if not: `pkill -f _cloud_worker.py`) |
Also verified: `claude plugin disable` stops capture (+1 vs +0 sessions) and a real `/compact` kept 5/5 planted facts (46,349 → 12,288 tokens). Not verified anywhere yet: Codex, behavior over several days or long sessions, Colima/OrbStack/Linux, the `.docx`/`.png` rendering (patched, not rendered).

### 21.6 Operating policy (summary of 19, 20, 20.1)
Briefing at start (≈ 1–1.5 k tokens, deterministic); consult Cognee `CHUNKS`, `top_k=3` whenever the briefing does not answer — before asking the user or assuming; handoff when a task ends; sync once per task/milestone; index what `CLAUDE.md` does not already carry; freshness via `scripts/memory_stale.py`; capture on with the caps above and **review consumption after one week** with `scripts/weekly_report.py` (decide keep / limit / off). Below ≈ 30 k tokens of corpus, plain Markdown reading is cheaper than Cognee (first A/B: 3.0×).

### 21.7 Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| `/health` 503 `Missing required pgvector credentials` | no `VECTOR_DB_*` under access control | set them (21.3) |
| API container exits at startup, email validation error | reserved email domain | use a real-looking domain, recreate |
| `Permission denied` on `/models/...` | root-owned named volume | use the thin image (`cognee.Dockerfile`) |
| MCP tools return 401 | Bearer vs API key | `COGNEE_API_AUTH_SCHEME=x-api-key` |
| `recall` 404 `Dataset(s) not found` | wrong dataset name (or a list passed as `datasets`) | pass `datasets` as a string equal to `memory_dataset` |
| Collector cannot write | distroless uid 10001, root-owned volume | `agents_telemetry_init` |
| Captures pile up in `spool/` | plugin worker kept the old environment | `pkill -f _cloud_worker.py` |
| Observer calls fail from the container | observer not running / token mismatch | `observer.sh start`, then `gen_env.sh` and recreate the API |
| Briefing cut off | over the 6,000-char cap | shorten sections; the footer is always kept |
| Memory answers come from Claude's own notes | native auto memory active in tests | disable it for the test run |
| Unexpected `codebase-*` dataset | plugin treats loopback as local | `COGNEE_CODE_AUTOINDEX=off`; delete the empty dataset |

## 22. Diagrams (Mermaid) and skills status

Flow diagrams (architecture, write path, read path, daily cycle, where session history is paid) live as Mermaid sources in `diagrams/*.mmd` (also `reference-implementation/docs/diagrams.md`, which GitHub renders); the PNGs were rendered with `@mermaid-js/mermaid-cli` (`-w 2400 -s 2`, theme in `mermaid-config.json`). `Cognee-memory-map.png` is now the architecture diagram of the installed system. The six custom skills are implemented (`project-memory-recall`, `-document`, `-handoff`, `-bootstrap`, `-maintain`, `-evaluate`) and installed with `install_skills.sh`/`install_project.py`; `bootstrap`, `maintain` and `evaluate` are procedures written from the tested scripts and have not yet had an end-to-end run of their own.



## 23. Where things run: the local data flow (v1.6)

Plain answer to "am I calling a Cognee API?": **no**. "Cognee" is a program you run yourself in Docker on your Mac (`agents_cognee_api`, bound to `127.0.0.1:45874`). There is no Cognee cloud account or server involved. The plugin setting `COGNEE_BACKEND=cloud` only means "HTTP client mode"; the server it talks to is yours.

| Step | Where it runs | Leaves the Mac? | Uses subscription tokens? |
|---|---|---|---|
| Split a document into chunks | `agents_cognee_api` (Docker) | no | no |
| **Compute embeddings** (768-d vectors) | same container, fastembed `jina-embeddings-v2-base-es` (downloaded once from Hugging Face, cached in the `/models` volume) | no | no |
| Store vectors / relational data | PostgreSQL + pgvector (Docker, one `ds_<dataset_id>` schema per dataset) | no | no |
| Store the knowledge graph | Ladybug `.lbug` file per dataset (volume) | no | no |
| **Summaries and concept extraction** at *index* time | observer on the Mac (`claude -p`, port 8017) → Anthropic | **yes** (the chunk text) | **yes** (~2 calls per chunk) |
| **Search / recall** (query → vector → nearest chunks) | API + PostgreSQL | no | no |
| MCP (`agents_cognee_mcp`, `127.0.0.1:45873`) | local "socket" that turns Claude Code's `recall`/`remember` tool calls into HTTP calls to the local API | no | no |
| Retrieved text inside the Claude Code conversation | Claude Code → Anthropic (as any text you show it) | yes | counts as normal conversation tokens |

Write path: `Markdown → sync_markdown.py (hash) → Cognee: chunk → local embeddings → pgvector; chunk text → observer → Claude → summaries/entities → graph`. Read path: `question → MCP/hook → Cognee: local embedding → nearest vectors in pgvector → chunks returned to Claude Code`. The only external dependency of the whole system is Claude itself, at indexing time.

## 24. Project language (v1.6)

Every installation must decide whether the project's memory documents are in **Spanish or English**, because the language selects the templates (`templates/<lang>/`), the `CLAUDE.md` memory section, the startup-briefing headings and the language of the evaluation questions. The installer never guesses silently:

1. `scripts/detect_language.py <repo>` samples README, `CLAUDE.md`, `AGENTS.md` and `docs/**/*.md` (stop-word heuristic, no network) and prints `LANG=<es|en|unknown> CONFIDENCE=<0-1>`. Exit 0 means confidence ≥ 0.75.
2. `install_project.py --lang auto` (default) uses a confident result and tells the user; when ambiguous (almost empty repo, mixed languages, confidence < 0.75) it **asks** — interactively on a TTY, otherwise it exits with code **3** and the message `AMBIGUOUS_LANGUAGE`, and **the agent must ask the user** and re-run with `--lang es|en`.
3. The choice is stored in `.agent-memory/project.yaml` (`language: es|en`; absent = `es` for projects created before v1.6). `memory_brief.py` reads it. The embedder is bilingual, so retrieval works in both languages; keep the evaluation set in the project language plus 2–3 questions in the other.
4. Tested: Spanish repo (confidence 0.90) → `es`; English sample → `en`; empty repo → exit 3; explicit `--lang en` → English templates, section "Project memory (Cognee)", briefing "Project memory (startup briefing…)"; re-running is idempotent.

## 25. Seed bundle (v1.6)

`seed-bundle/` is the single entry point for an agent that must install this system without prior knowledge: `AGENT_PROMPT.md` (the message to paste), `SEED.md` (phased runbook with approval points), `seed.sh` (`doctor`, `machine`, `project`, `panel`, `verify`), `manifest.yaml` (tested versions, ports, phases, prohibitions) and a copy of this specification. Phases: 0 scope → 1 doctor → 2 **language (ask if ambiguous)** → 3 machine (once per Mac, needs approval) → 4 project → 5 pilot corpus (`project-memory-bootstrap`) → 6 index (needs approval; costs tokens) → 7 dashboard → 8 verify and hand over. `seed.sh` never edits global Claude Code settings unless `--with-plugin` is passed; it prints the three `claude plugin`/`claude mcp` commands otherwise. Tested: `doctor` and `verify` against the live pilot; `project` language paths as in 24.

## 26. Management Memory dashboard (v1.6)

Separate repository (`management_memory`, bundled in the kit as `panel/`, no secrets: its `.env` is generated per Mac by `scripts/setup.py` and git-ignored; history audited Oct 29, 2026) and separate Compose project: a **read-only** internal dashboard at `127.0.0.1:45876` to decide what to keep, compact or delete. Pages: summary and health, knowledge bases (size, chunks, vectors, reingest cost, per-document weight and advice), vectors (what is stored and where, per `ds_*` schema), graph (Cytoscape), PostgreSQL browser and read-only SQL console, search test, tokens and cost (three sources), API calls and containers, sync registry, guide and glossary.

- **Read-only by construction:** PostgreSQL role `mm_reader` (read-only transactions, 15 s statement timeout, single-statement validator); Docker access only through a `socket-proxy` with a regex allowlist (logs/stats/inspect GET); mounts read-only; non-root container; Host-header allowlist (anti DNS-rebinding), CSP, `no-store`; all dynamic text rendered with `textContent`.
- **Token sources (they measure different things):** (1) observer log — complete, what Cognee spends indexing; (2) Claude Code OpenTelemetry via the collector — authoritative `api_request` log events, but **only sessions started with real `OTEL_*` environment variables** (`scripts/claude-memory <project>`; the `env` block of `settings.json` does not work); metrics under-count short sessions; (3) Cognee session stats — usually zero because the observer uses the subscription. Subscription quota remaining is not observable from outside.
- **Memory usage page (v1.6):** `scripts/usage_scan.py` reads the Claude Code transcripts (`~/.claude/projects/*/*.jsonl`, read-only, metadata only: timestamp, session, truncated query, dataset, ok/error, latency, result size — never the returned text) and writes `view/usage.jsonl`; it runs from the SessionEnd/PreCompact checkpoint hook. It reports briefing injections (SessionStart hook output), recalls (MCP `recall` tool and the `project-memory-recall` skill), writes, and the plugin's own "recall hit rate". It proves the memory *is used and answers*; whether it *helps* still needs `memctl.sh eval` and the cost A/B. First real finding: one early MCP recall failed with 404 (before the dataset-name fix), later ones succeeded.
- **Host resources page (v1.6), on demand, nothing resident:** a container cannot see the Mac, and a polling process was rejected as an unwanted load. `scripts/host_stats_launchagent.sh install` registers a launchd **socket-activated** agent on `127.0.0.1:8018` (`inetdCompatibility`, `Nice 10`): launchd listens for free and runs `host_stats.py --inetd` once per connection (~2 s: CPU, RAM, compressed, swap, memory pressure, disk, load, battery, top processes), which exits after answering. The dashboard's "Medir el Mac ahora" button POSTs to it through `host.docker.internal`; the handler rejects any `Host` header other than `host.docker.internal|127.0.0.1|localhost:8018` (anti DNS-rebinding). Samples live only in the dashboard's memory for the session (no files, no history on disk). Tested: idle = no `host_stats` process; one request = one short process. Docker side is read when the page opens, from the engine through the read-only proxy (`/info`, `/system/df`, per-container stats): VM CPU/RAM, images, volumes, build cache.
- Installed by `seed.sh panel --yes`, which clones the public repo (or `git pull --ff-only` if present), installs the on-demand launchd socket, then runs `docker compose up -d --build` in its repo; `scripts/setup.py` creates the read-only role and `.env`.
