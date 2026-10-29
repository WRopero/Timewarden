# Estrategia para no quemar tokens

Fuentes: Cognee (nota tecnica de costo, skill `cognee-performance`, docs de search types) y medicion propia (2026-10-26).

## Donde se va el costo
| Etapa | Costo | Evidencia |
|---|---|---|
| **Ingesta (`cognify`)** | Dominante. ~2 llamadas LLM por chunk (resumen ~27 % + grafo ~73 %) | Cognee: ~23–25× los tokens del corpus. Medido aqui: ~307 000 tokens para ~4 100 de corpus (~75×; cada `claude -p` arrastra ~23 k de prompt cacheado) |
| Consulta `CHUNKS` | 0 llamadas LLM | docs search types |
| Consulta `GRAPH_COMPLETION` (defecto de MCP sin `search_type`) | ≥1 llamada | idem; COT/DECOMPOSITION/CONTEXT_EXTENSION: varias |
| Inyeccion por prompt del plugin | hasta 9 000 caracteres (~2 300 tokens) por prompt | README plugin (`COGNEE_INJECT_MAX_CHARS`) |
| Verificar leyendo codigo | tokens de lectura por archivo | A/B propio: B costo 3× A por esto y por el recall |

`chunkSize` **no** ayudo con documentos pequeños (3 chunks con 2000 o 4000 tokens; 6–7 llamadas): el costo sigue al numero de parrafos/secciones.

## Reglas
1. **Cognee solo donde Markdown directo no alcanza.** Corpus < ~30 k tokens: cargarlo/leerlo directo (CLAUDE.md, grep). Break-even de ingesta con corpus de ~4 k tokens: >100 consultas. Cognee compensa con corpus grande, varios proyectos/agentes o relaciones entre documentos (la propia Cognee reporta break-even de ~23–26 consultas con corpus de 16–200 k tokens).
2. **No duplicar lo que ya esta en contexto.** CLAUDE.md se carga en cada sesion; indexar copias suyas paga ingesta sin beneficio. Indexar lo que *no* esta ahi (historial de decisiones, runbooks, specs).
3. **Ingestar poco y en lote:** `memctl.sh sync` una vez por tarea/hito, nunca por edicion. El registro por hash ya evita reprocesar (0,28 s, 0 llamadas). Documentos densos y concisos: menos parrafos = menos chunks.
4. **Consultar bajo demanda:** recall explicito (skill) con `search_type=CHUNKS`, `top_k` 3–5, una vez por tarea. Sin recall automatico por prompt: la captura esta apagada y el dataset de sesiones vacio (el hook inyecta ~nada); si algun dia se activa, `COGNEE_INJECT_MAX_CHARS=3000`, `COGNEE_RECALL_PASSAGE_CHARS=600`.
5. **Frescura por Git, no por lectura:** `scripts/memory_stale.py` (0 tokens) decide si hace falta abrir codigo.
6. **Apagado de extras (aplicado):** `AUTO_FEEDBACK=false`, `IMPROVE_AUTO_ENABLED=false` (servidor), `COGNEE_AUTO_IMPROVE_EVERY=0` (plugin), captura de sesiones off, `CODE_AUTOINDEX=off`.
7. **Medir antes de ampliar:** `analytics` (A/B) + `memctl.sh eval`. Un ahorro negativo es un resultado valido.

## Palancas que existen pero no se aplicaron (y por que)
- `extractor="gliner"` (grafo local sin LLM): solo en el SDK `remember()`, no en la API REST de 1.6.5.
- Modelos baratos por etapa (`LLM_EXTRACTION_MODEL`...): el observer ya usa `haiku`, el mas barato disponible.
- `data_per_batch`/`chunks_per_batch`: reparten carga, no reducen tokens.
- Prompt caching propio de Cognee: no documentado por ellos.
