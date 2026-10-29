# OpenSpec: quién dirige el trabajo

[OpenSpec](https://github.com/Fission-AI/OpenSpec) es desarrollo guiado por especificaciones. En Timewarden es **obligatorio y forma parte de la instalación**: ningún cambio de producto se implementa sin un cambio de OpenSpec activo.

## La regla (se escribe en el `CLAUDE.md` del proyecto)
Toda funcionalidad nueva, cambio de comportamiento, refactor no trivial o cambio de datos/infraestructura sigue:

1. `/opsx:propose` → proposal (por qué y qué cambia), specs (comportamiento verificable), design (decisiones) y tasks.
2. **Revisión del usuario.** Nada se implementa antes.
3. `/opsx:apply` → implementa las tareas.
4. `/opsx:archive` → los specs del cambio se fusionan en `openspec/specs/` (la verdad vigente).
5. `memctl.sh sync . --apply` una vez → los specs entran a la memoria.

**Excepciones** (sin cambio): erratas, formato, comentarios y hotfix urgente (se documenta después con un cambio).

## Cómo se une con la memoria
| Pieza | Qué hace |
|---|---|
| Fuentes de indexación | `openspec/specs/**` (vigentes, `verified`), `openspec/changes/**` (activos `draft`, archivados `verified`). No requieren frontmatter |
| Briefing | Lista cuántos specs vigentes hay y los **nombres de los cambios activos** |
| Regla de ambigüedad | Antes de proponer, el agente consulta la memoria y los specs; si código y spec difieren, pregunta |
| Recuperación | Un chunk de un spec trae `type=openspec-spec` y su ruta, para citarlo |

## Instalación
`seed.sh doctor` comprueba el CLI `openspec`; `seed.sh project` ejecuta `openspec init --tools claude --language <es|en>` en el repo (salvo `--no-openspec`). Si falta el CLI el agente debe proponerte instalarlo (ver `seed-bundle/SEED.md`).

## Por qué este orden
La memoria responde *qué pasó y por qué*; OpenSpec fija *qué debe hacer el sistema*. Juntas evitan los dos fallos típicos de un agente: olvidar decisiones y construir sin acuerdo.
