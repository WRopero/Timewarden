## Why

El bundle de instalación de la memoria de proyecto (Cognee en Docker + hooks + skills) nació en un proyecto web concreto y arrastra su nombre, rutas absolutas y supuestos (Django/Next.js). Se quiere compartir con compañeros que trabajan, además, en **proyectos de datos** (BigQuery + Dataform, Snowflake + dbt), donde lo que importa recordar es distinto: linaje, particionado, costo de consultas, entornos, permisos y versiones de paquetes/adaptadores. También falta memoria de **seguridad y versiones** (qué hay instalado, cuándo y por qué cambió), de **despliegues por rama** y de los **specs de OpenSpec**.

## What Changes

- El bundle detecta el tipo de proyecto, **pregunta cuando es ambiguo** y aplica un perfil (dbt/Snowflake, Dataform/BigQuery, SQL/BigQuery con Terraform, aplicación web, genérico).
- Perfiles de datos con las reglas que el agente debe respetar (costo de BigQuery, particiones, entornos, grants, tests de dbt/Dataform, secretos fuera del repo).
- Registro determinista de dependencias y versiones con historial (motivo `security` vs `upgrade`) y auditoría de vulnerabilidades (OSV) lanzada automáticamente por el hook de arranque, con pendientes visibles en el briefing.
- Registro de despliegues por entorno y estado por rama (ya implementado; se formaliza).
- Los specs y cambios de OpenSpec se indexan en la memoria y el briefing lista los cambios activos.
- Regla: ante ambigüedad, consultar la memoria antes de decidir o preguntar.
- **BREAKING**: el bundle deja de depender de rutas, nombres de proyecto o cuentas personales; se distribuye como `.zip` autocontenido (incluye el panel Management Memory) con instalación relocalizable.

## Capabilities

### New Capabilities
- `project-type-detection`: detectar tipo de proyecto, confianza y pregunta obligatoria si es ambiguo.
- `data-project-profiles`: reglas y plantillas de memoria para proyectos de datos (dbt/Snowflake, Dataform/BigQuery).
- `dependency-security-memory`: versiones instaladas, historial de cambios y auditoría de vulnerabilidades automática.
- `deployment-ledger`: qué commit está desplegado por entorno y estado de cada rama.
- `openspec-memory`: specs y cambios de OpenSpec como parte de la memoria.
- `ambiguity-recall-rule`: consultar la memoria cuando la tarea es ambigua.
- `portable-bundle`: paquete `.zip` neutral, relocalizable y verificable.

### Modified Capabilities
<!-- Primera spec del repositorio: no hay capacidades previas en openspec/specs -->

## Impact

- Código: `scripts/` (nuevos `detect_project_type.py`, `memory_deps.py`, `memory_audit.py`, `memory_deploy.py`, `package_bundle.sh`), `seed-bundle/`, `skills/`, `templates/`, `profiles/`.
- Proyectos ya instalados: el contrato (`.agent-memory/project.yaml`) gana campos opcionales; sin ellos todo sigue funcionando.
- Red: la auditoría consulta `api.osv.dev` (solo nombres y versiones de paquetes); si no hay red falla en silencio.
- Fuera de alcance: soporte Windows/Linux (solo se probó macOS + Docker Desktop), ejecutar `dbt`/`dataform` o conectar a BigQuery/Snowflake desde la memoria.
