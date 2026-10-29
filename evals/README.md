# Retrieval Evaluations

`memctl.sh eval <repo>` reads `evals/cases.<project_id>.jsonl` (one JSON line per question):

| Field | Meaning |
|---|---|
| `id` | Question identifier |
| `lang` | `es` or `en` (it's best to mix them to check the bilingual embedder) |
| `q` | Question |
| `expect` | List of `doc_id`s where the answer is found (any one in the top-5 counts) |
| `unanswerable` | `true` = negative control: it must not return anything relevant |

Copy `cases.example.jsonl` to `cases.<project_id>.jsonl` and write ~20 questions with an expected source over the project's real corpus (skill `project-memory-evaluate`). Goal: ≥ 85% document recall@5.
