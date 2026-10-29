---
name: project-memory-bootstrap
description: Use to onboard a new repository into project memory or to reconstruct its initial map. Installs the memory contract and hooks, drafts project.md and architecture.md from real documentation, and proposes a 10-20 document pilot corpus. Do not use for repositories that already have .agent-memory/project.yaml.
---

# project-memory-bootstrap

> `<MS>` = ruta del sistema de memoria: campo `memory_system` de `.agent-memory/local.yaml` (local a cada maquina).

Incorpora un repositorio a la memoria sin escanear el disco ni inventar contenido.

## Procedimiento
1. Confirma el alcance con el usuario: un solo repositorio, su `project_id` (estable, no la ruta del checkout) y datos que no deben entrar (clientes, bancarios).
2. Instala el contrato: `python3 -I <MS>/scripts/install_project.py <repo> --project-id <id>` (idempotente; anade `--no-capture` si la captura de sesiones debe quedar apagada).
3. Lee **documentacion real**: README, `CLAUDE.md`, specs, runbooks, configuracion. Prefiere lo escrito a lo inferido del codigo.
4. Redacta `docs/agent-memory/project.md` (seccion *Objetivo* de 1 a 3 frases: la cita el briefing) y `architecture.md` con `status: draft`, citando `source_paths` reales y `source_commit` = `git rev-parse --short HEAD`.
5. Propone el corpus piloto (10-20 documentos): decisiones, implementaciones, reglas de negocio, runbooks **que no esten ya en `CLAUDE.md`**. Lista las lagunas de documentacion en lugar de rellenarlas.
6. Si el usuario aprueba: crea los documentos con las plantillas de `.agent-memory/templates/`, luego `memctl.sh sync <repo>` (plan) y, con su visto bueno, `--apply`. Avisa del costo (~2 llamadas a Claude por chunk).
7. Crea 20 preguntas con fuente esperada en `<MS>/evals/cases.<id>.jsonl` y corre `memctl.sh eval <repo>`.

## Salida
Registro del proyecto, `project.md`, `architecture.md`, lista de lagunas, resultado del `eval`.

## Limites
- No escanees el disco, no ingieras dependencias ni datasets de clientes, no afirmes entender todo el repositorio.
- Nada de credenciales ni datos reales sensibles en los documentos.
- Documentos sin validar quedan `draft`; `verified` solo tras ejecutar la comprobacion.
