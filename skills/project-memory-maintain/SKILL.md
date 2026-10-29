---
name: project-memory-maintain
description: Use when a decision was corrected, the architecture changed, or when auditing stale memory in a project with .agent-memory/project.yaml. Detects obsolete, duplicate or contradictory notes, marks supersession, and re-syncs the index incrementally.
---

# project-memory-maintain

> `<MS>` = ruta del sistema de memoria: campo `memory_system` de `.agent-memory/local.yaml` (local a cada maquina).

Mantiene la memoria veraz: reemplaza, no acumula versiones contradictorias.

## Procedimiento
1. **Auditar sin tokens:** `python3 -I <MS>/scripts/memory_stale.py <repo>` lista `OBSOLETO` (los `source_paths` cambiaron desde `source_commit`) y `SIN-FUENTE`.
2. Para cada `OBSOLETO`: abre solo los archivos listados, compara con la nota y decide: actualizar (nuevo `source_commit`, `updated_at`), reemplazar (nota nueva con `supersedes: [id-anterior]` y la anterior pasa a `status: superseded`) o archivar (`archived`).
3. Busca duplicados y contradicciones entre notas (mismo tema, distinta regla). **No resuelvas contando menciones**: contrasta con el codigo/Git o pregunta al dueno de negocio. Si no hay evidencia, deja ambas marcadas y anota la pregunta abierta en un handoff.
4. Cambios de decision: crea la decision nueva, no edites la historia de la anterior.
5. Sincroniza **una vez** al terminar: `memctl.sh sync <repo>` (plan) y `--apply`. Verifica que la version nueva se recupera y la vieja no (`memctl.sh eval <repo>` o un `recall` puntual).
6. Informa: documentos cambiados, estado del sync (indexed/unverified/error), notas obsoletas pendientes.

## Limites
- No borres un dataset entero para corregir una nota; `sync` ya reemplaza por `data_id`.
- Antes de operaciones destructivas amplias, muestra el alcance y pide confirmacion. Nunca `forget` con `everything`.
- No marques `verified` sin evidencia de validacion.
