---
name: project-memory-handoff
description: Use when switching session or agent, pausing a task, or before context compaction in a project with .agent-memory/project.yaml. Preserves observable task state (objective, constraints, files, tests, decisions, next action) so work can resume.
---

# project-memory-handoff

> `<MS>` = ruta del sistema de memoria: campo `memory_system` de `.agent-memory/local.yaml` (local a cada maquina).

Preserva el estado observable de una tarea. No guarda razonamiento interno del modelo.

## Procedimiento
1. Captura: objetivo, rama y commit (`git branch --show-current`, `git rev-parse --short HEAD`), restricciones, archivos tocados, cambios sin commit, pruebas y resultados, decisiones nuevas con su fuente, intentos fallidos, trabajo pendiente y **siguiente accion**.
2. Marca explicitamente lo no validado.
3. Escribe un archivo por tarea: `docs/agent-memory/handoffs/<fecha>-<tarea>.md` (compartible) o, si es privado, `docs/agent-memory/handoffs/_local/` (esta excluido del indice). Nunca un unico archivo global.
4. **Despliegue:** si en la sesion se desplego algo, comprueba la salud y registralo con `python3 -I <MS>/scripts/memory_deploy.py record <repo> <entorno> --commit <sha> --note "..."`; el briefing compara por rama que esta desplegado y que no. Si no se desplego, no registres nada y dilo en el handoff (rama, commit, "sin desplegar").
5. Al retomar: valida rama/commit con el estado real antes de confiar en el handoff; contrastalo con el repo.

## Compactacion
`PreCompact` solo persiste estado ya disponible; no puede invocar esta skill. Mantén el handoff al dia **durante** el trabajo y antes de acercarte al limite de contexto.

## Limites
- Un checkpoint no es una conclusion validada. Nada de secretos.
