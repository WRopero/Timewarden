---
name: project-memory-evaluate
description: Use after a pilot, a model/version change, or when memory quality or cost is in doubt in a project with .agent-memory/project.yaml. Measures retrieval quality, freshness, isolation, continuity and token consumption, and compares memory against reading the Markdown directly.
---

# project-memory-evaluate

> `<MS>` = ruta del sistema de memoria: campo `memory_system` de `.agent-memory/local.yaml` (local a cada maquina).

Mide si la memoria ayuda y cuanto cuesta; un ahorro negativo es un resultado valido.

## Procedimiento
1. **Recuperacion:** `<MS>/scripts/memctl.sh eval <repo>` (20 preguntas ES/EN con `doc_id` esperado; objetivo >= 17/20 en top 5, p95 < 3 s). Las preguntas sin respuesta solo se reportan: abstenerse es decision del agente.
2. **Frescura:** `memory_stale.py <repo>`; cuenta notas `OBSOLETO` y `SIN-FUENTE`.
3. **Aislamiento (tras cambios de version o de dataset):** dos datasets de prueba con un hecho distinto cada uno; consulta cruzada en ambos sentidos; `forget` de uno y comprueba que el otro sigue intacto.
4. **Continuidad:** sesion nueva sin herramientas y con `--settings '{"autoMemoryEnabled":false}'`; pregunta decisiones, reglas y pendientes; compara con la verdad conocida.
5. **Consumo:** `python3 -I <MS>/scripts/weekly_report.py` (observer y sesiones) y, para A/B, lanza las variantes con `scripts/claude-memory <id> A|B -- ...` y corre `scripts/dc.sh --profile eval run --rm agents_analytics report --project <id>`.
   - A = leer el mismo Markdown sin plugin ni MCP; B = con memoria. Mismo commit, modelo y pregunta; varias repeticiones; separa ingesta (una vez) de consulta.
6. Reporta resultados **reales** con sus limites (tamano de muestra, que no se midio) y recomienda: seguir, ajustar o reducir.

## Limites
- La respuesta de otro LLM no es la unica verdad de referencia; contrasta con fuentes.
- Contar documentos no demuestra ahorro; una tarea fallida con menos tokens no es ahorro.
- Las pruebas de historia deben desactivar la memoria nativa de Claude o miden otra cosa.
