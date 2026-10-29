# OpenSpec: who directs the work

[OpenSpec](https://github.com/Fission-AI/OpenSpec) is specification-driven development. In Timewarden it is **mandatory and part of the installation**: no product change is implemented without an active OpenSpec change.

## The rule (written into the project's `CLAUDE.md`)
Every new feature, behavior change, non-trivial refactor, or data/infrastructure change follows this flow:

1. `/opsx:propose` → proposal (why and what changes), specs (verifiable behavior), design (decisions), and tasks.
2. **User review.** Nothing is implemented before it.
3. `/opsx:apply` → implements the tasks.
4. `/opsx:archive` → the change's specs are merged into `openspec/specs/` (the current source of truth).
5. `memctl.sh sync . --apply` once → the specs enter the memory.

**Exceptions** (no change needed): typos, formatting, comments, and urgent hotfixes (documented afterward with a change).

## How it connects with the memory
| Piece | What it does |
|---|---|
| Indexing sources | `openspec/specs/**` (current, `verified`), `openspec/changes/**` (active `draft`, archived `verified`). They don't require frontmatter |
| Briefing | Lists how many current specs there are and the **names of the active changes** |
| Ambiguity rule | Before proposing, the agent consults the memory and the specs; if code and spec differ, it asks |
| Retrieval | A chunk from a spec carries `type=openspec-spec` and its path, so it can be cited |

## Installation
`seed.sh doctor` checks for the `openspec` CLI; `seed.sh project` runs `openspec init --tools claude --language <es|en>` in the repo (unless `--no-openspec` is given). If the CLI is missing, the agent must offer to install it for you (see `seed-bundle/SEED.md`).

## Why this order
The memory answers *what happened and why*; OpenSpec defines *what the system must do*. Together they avoid the two typical failures of an agent: forgetting decisions and building without agreement.
