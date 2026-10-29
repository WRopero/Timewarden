---
name: project-memory-document
description: Use after a significant completed change, a confirmed decision, a validated solution, or when the user says "document/remember this" in a project with .agent-memory/project.yaml. Writes or updates Markdown under docs/agent-memory/ and queues synchronization to Cognee.
---

# project-memory-document

> `<MS>` = ruta del sistema de memoria: campo `memory_system` de `.agent-memory/local.yaml` (local a cada maquina).

Guarda conocimiento verificable como Markdown revisable; Cognee solo lo indexa.

## Procedimiento
1. Decide el tipo: `implementations/` (cambio + evidencia), `decisions/` (decision + alternativas), `runbooks/`, `business/` (definiciones). Actualiza una nota existente si aplica en vez de crear otra.
2. Usa el esquema del frontmatter: `id, project_id, type, status, created_at, updated_at, source_commit (hash real: git rev-parse --short HEAD), source_paths, supersedes, tags`.
3. Redacta: problema y alcance, implementacion, decision y razon, alternativas y fallos, **evidencia de validacion**, limitaciones, pendientes.
4. Separa observaciones de hipotesis. Una respuesta de Claude no es evidencia; un test ejecutado si.
5. `status: verified` solo si ejecutaste la validacion. Si no, `draft`. Si reemplaza algo, rellena `supersedes` y marca el anterior `superseded`.
6. Sincroniza **una sola vez por tarea o hito** (no tras cada edicion; cada chunk nuevo cuesta ~2 llamadas a Claude): `<MS>/scripts/memctl.sh sync <repo> --apply`
   y reporta el estado real: guardado local / enviado / indexado y recuperable.

## Limites
- Nunca guardes credenciales, `.env`, tokens, datos personales de terceros ni datos bancarios reales.
- No crees una nota por cada respuesta; solo cambios significativos.
- No ejecutes `forget` con `everything` ni borres datasets.
