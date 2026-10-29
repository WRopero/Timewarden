# Continuidad entre sesiones ("retomar como si no hubiera cerrado")

Principio: lo que **siempre** se necesita se inyecta una vez al abrir (barato y determinista); lo profundo se consulta a Cognee **solo si hace falta**.

| Capa | Que aporta | Cuando | Costo |
|---|---|---|---|
| 1. `CLAUDE.md` | reglas del proyecto, stack, fases | cada sesion (nativo) | ya incluido |
| 2. Briefing (`memory_brief.py`, hook SessionStart: startup/resume/clear/compact) | objetivo, decisiones vigentes, reglas de negocio, pendientes, ultimo handoff, notas obsoletas (Git) | al abrir y tras compactar | ~1 000 tokens, 0 llamadas LLM, 0 consultas a Cognee |
| 3. Checkpoint (`memory_checkpoint.py`, hooks SessionEnd + PreCompact) | rama, cambios sin commit, ultimos commits y ultimos pedidos del usuario | al cerrar/compactar | 0 tokens |
| 4. Handoff semantico (skill `project-memory-handoff`, lo pide CLAUDE.md al cerrar un hito) | decisiones, por que, pruebas, siguiente accion | al terminar una tarea | ~1 turno |
| 5. Memoria duradera (`project-memory-document` + `memctl.sh sync`) | decisiones/implementaciones/reglas que deben sobrevivir meses | por hito | ingesta (la parte cara) |
| 6. Cognee `recall` (CHUNKS, top_k 3) | historial profundo que no cabe en el briefing | bajo demanda, 1×/tarea | 0 LLM + lo recuperado |

## Flujo de un dia
Abres Claude en el proyecto → briefing cargado (sabe decisiones, negocio, pendientes y donde quedaste) → trabajas → al cerrar un hito: handoff (+ documentar y sync si hubo decision) → cierras; el hook deja el checkpoint → manana el briefing incluye ese handoff.

## Limites honestos
- El briefing es **determinista**: resume lo que esta escrito en `docs/agent-memory/`. Si algo no se documento ni entro en un handoff, no se recuerda. La disciplina clave es el handoff/documentar al cerrar.
- El checkpoint automatico solo sabe de Git y de tus ultimos pedidos; no sabe *por que* decidiste algo.
- Tope del briefing 6 000 caracteres: con muchos documentos hay que priorizar (hoy: solo decisiones `verified|draft`, reglas, 10 pendientes, 1 handoff, 6 obsoletos).
- Probado: sesion nueva sin herramientas respondio decisiones, reglas y pendientes (1 turno, $0,0075). No probado: varios dias de uso real.
- Se apagó la preferencia/inyeccion por prompt del plugin y se restauro `autoMemoryEnabled` global (el plugin lo habia puesto en `false`).
