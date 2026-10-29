## Context

El sistema ya funciona en un proyecto piloto: Cognee en Docker, un briefing determinista que se inyecta en `SessionStart`, un checkpoint en `SessionEnd/PreCompact`, skills `project-memory-*`, y un panel de solo lectura. Este cambio lo vuelve distribuible y lo especializa.

## Goals / Non-Goals

**Goals:** portabilidad real (un `.zip`), perfiles de datos, memoria de seguridad/versiones con auditoría automática, despliegues por rama, OpenSpec indexado.
**Non-Goals:** soportar sistemas distintos de macOS + Docker Desktop; conectarse a BigQuery o Snowflake; reemplazar `npm audit`/`pip-audit` en CI.

## Decisions

1. **Detección por evidencias ponderadas, no por una sola marca.** `detect_project_type.py` puntúa archivos (p. ej. `dbt_project.yml`, `workflow_settings.yaml`, `.sqlx`, `*.tf` con `google_bigquery_*`) y devuelve `PROFILE`, `CONFIDENCE` y `EVIDENCE`; código de salida 3 = preguntar (mismo contrato que el idioma). Alternativa descartada: preguntar siempre — añade fricción en casos obvios.
2. **Perfiles como datos (`profiles/<id>/`)**: `profile.yaml` (exclusiones, fuentes extra, lockfiles extra), `rules.<lang>.md` (se inyecta al `CLAUDE.md`) y plantillas. Añadir un perfil no requiere tocar código.
3. **OSV como fuente de auditoría**: una sola API sin instalar herramientas, cubre PyPI y npm con la versión exacta del lock. Sale del equipo solo nombre+versión. Alternativa: `pip-audit`/`npm audit` (requieren instalar y cubren un ecosistema cada uno); se mantiene `npm audit` como contraste manual.
4. **Hook de arranque lanza la auditoría desacoplada** (`start_new_session`), una vez cada 24 h, para no bloquear la sesión. El resultado vive fuera del repositorio; solo el documento de pendientes se versiona.
5. **Registro de dependencias solo de directas** + historial; las transitivas se auditan pero no se inventarían (evita ruido).
6. **Bundle relocalizable**: raíz resuelta desde la ubicación del script (`MEMORY_SYSTEM_HOME` para sobrescribir) y escrita en `project.yaml` (`memory_system:`) para que skills y reglas no lleven rutas fijas. El panel se incluye como código fuente en el `.zip`.
7. **Empaquetado con lista blanca + escaneo**: `package_bundle.sh` copia solo lo declarado y falla si encuentra términos prohibidos o patrones de secretos.

## Risks / Trade-offs

- [Reglas de datos genéricas pueden no encajar con la convención del equipo] → los perfiles son texto editable en el proyecto, y el agente debe preguntar ante dudas.
- [OSV puede listar avisos que no aplican al uso real] → archivo de excepciones y verificación manual; el briefing solo prioriza, no bloquea.
- [El escaneo de neutralidad puede dar falsos positivos] → lista de términos configurable en el script.
