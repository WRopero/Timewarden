---
name: project-memory-recall
description: Use when starting a task, resuming work, a requirement or design decision is ambiguous (query BEFORE deciding or asking), asking "why did we decide X", or investigating a known issue in a project that has .agent-memory/project.yaml. Retrieves project background from Cognee scoped to that project's dataset, then verifies it against the current repository.
---

# project-memory-recall

> `<MS>` = ruta del sistema de memoria: campo `memory_system` de `.agent-memory/local.yaml` (local a cada maquina).

Recupera contexto del proyecto desde la memoria (Cognee) y lo contrasta con el codigo actual.

## Procedimiento
1. Lee `.agent-memory/project.yaml` del repo: usa `memory_dataset` (nunca otro dataset) y `max_recall_results`.
2. Si existe un handoff local reciente (`docs/agent-memory/handoffs/` o el checkpoint local), leelo primero.
3. Busca con la herramienta MCP `recall` (servidor `agents_cognee`):
   `query=<pregunta concreta>`, `datasets="<memory_dataset>"` (**string, no lista**), `search_type="CHUNKS"`, `top_k=5`.
   Un `404 Not Found` casi siempre significa un nombre de dataset inexistente: copia `memory_dataset` literal de `project.yaml`
   (p. ej. `mi-proyecto-knowledge`, no `mi-proyecto`). Omitir `search_type` devuelve una respuesta sintetizada por grafo (usa mas LLM).
   Cada fragmento comienza con `[memoria-proyecto] ... doc_id=... status=... path=...`: usa `path` como fuente.
4. Descarta o etiqueta lo que tenga `status: superseded|archived` y desconfia de `draft`.
5. **Verifica frescura sin gastar tokens:** `python3 -I <MS>/scripts/memory_stale.py <repo> <ruta del doc>`.
   - `FRESCO` (los `source_paths` no cambiaron desde `source_commit`): usa la memoria tal cual, **no abras codigo**.
   - `OBSOLETO`: abre solo los archivos listados y reporta la diferencia; la memoria no es autoridad.
   - `SIN-FUENTE`: tratalo como `draft`; verifica solo si la decision es critica.
6. Responde corto: decisiones, restricciones, fuentes (rutas), incertidumbres y frescura.

## Limites
- Consultar es barato (CHUNKS no usa LLM): hazlo cuando el briefing no alcance y antes de preguntar al usuario o asumir. No repitas la misma pregunta ni consultes lo que el briefing ya dice; `top_k=3` salvo que falte evidencia.
- No consultes datasets de otros proyectos/clientes ni inyectes documentos completos (maximo ~1.500 tokens).
- No uses `forget` ni `remember` desde esta skill (solo lectura).
- Si no hay evidencia, dilo y sigue con inspeccion directa; no inventes.
- Si Cognee no responde, lee `docs/agent-memory/` directamente (el Markdown es la fuente canonica).
