# Evaluaciones de recuperación

`memctl.sh eval <repo>` lee `evals/cases.<project_id>.jsonl` (una línea JSON por pregunta):

| Campo | Significado |
|---|---|
| `id` | Identificador de la pregunta |
| `lang` | `es` o `en` (conviene mezclar para comprobar el embedder bilingüe) |
| `q` | Pregunta |
| `expect` | Lista de `doc_id` donde está la respuesta (cualquiera en el top-5 cuenta) |
| `unanswerable` | `true` = control negativo: no debe devolver nada relevante |

Copia `cases.example.jsonl` a `cases.<project_id>.jsonl` y escribe ~20 preguntas con fuente esperada sobre el corpus real del proyecto (skill `project-memory-evaluate`). Objetivo: ≥ 85 % de recall@5 de documento.
