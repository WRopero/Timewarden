# Proyectos de datos: BigQuery, Dataform, Snowflake y dbt

OpenMemory funciona igual en cualquier repositorio, pero en datos lo que importa recordar y vigilar es distinto: **costo de cada consulta, entornos, linaje, calidad, permisos y versiones de las herramientas**. Para eso existen los *perfiles por capas*.

## Cómo decide qué tipo de proyecto es
`scripts/detect_project_type.py` puntúa evidencias en el repo y devuelve capas, confianza y evidencias. **Si no está claro, el instalador sale con código 3 y el agente te pregunta**; nunca adivina.

| Evidencia | Capa |
|---|---|
| `dbt_project.yml` (+ `packages.yml`, `models/`) | `dbt` |
| `dbt-snowflake` en requirements / `type: snowflake` en un perfil | `snowflake` |
| `dbt-bigquery` / `type: bigquery` | `bigquery` |
| `workflow_settings.yaml` o `dataform.json`, archivos `.sqlx`, `@dataform/core` | `dataform` (+ `bigquery`, porque Dataform corre sobre BigQuery) |
| Terraform `google_bigquery_*`, cliente `google-cloud-bigquery`, `.sql` con `` `proyecto.dataset.tabla` `` | `bigquery` |
| Conector/SDK de Snowflake | `snowflake` |
| `package.json` con framework web, `manage.py`, Django/FastAPI/Flask | `webapp` |

Combinaciones típicas: `dbt,snowflake` · `dbt,bigquery` · `dataform,bigquery` · `bigquery` · `snowflake`.

**Casos en los que pregunta:** dbt sin adaptador detectable; dbt con evidencias de dos warehouses; Dataform junto a evidencias de Snowflake; repositorio sin evidencias reconocibles; dbt y Dataform a la vez. Puedes forzarlo: `seed.sh project <repo> <id> --profile dataform,bigquery`.

## Qué cambia por capa
| Capa | Reglas que el agente debe respetar (se escriben en el `CLAUDE.md` del proyecto) | Excluido de la memoria |
|---|---|---|
| **dbt** | `ref()`/`source()` siempre; `profiles.yml` fuera del repo y no se lee; **nunca `run/build/seed/snapshot` contra `prod` sin aprobación**; explorar con `compile`, `ls`, `show`, `--empty`; CI con `state:modified+ --defer`; tests y `contract` en marts; incrementales con `unique_key`; `--full-refresh` en tablas grandes requiere aprobación | `profiles.yml`, `target/`, `dbt_packages/`, `logs/` |
| **dataform** | `ref()`/`resolve()` siempre; `dataform compile` antes de ejecutar; `run --dry-run`; **no ejecutar ni reprogramar workflows de producción sin aprobación**; entornos por proyecto o `schemaSuffix`; assertions; incrementales con `uniqueKey` y `updatePartitionFilter` | credenciales, `node_modules/`, cuentas de servicio |
| **bigquery** | **dry run y bytes estimados antes de consultas nuevas o pesadas**; nada de `SELECT *`; partición + `require_partition_filter` y clustering; misma *location*; IAM mínimo y sin llaves JSON en el repo; Terraform: `plan` antes de `apply`, **`apply`/`destroy` solo con aprobación** | cuentas de servicio, `*.tfstate`, `*.tfvars`, `.terraform/` |
| **snowflake** | Costo = créditos: tamaño de warehouse por carga, `AUTO_SUSPEND`, `QUERY_TAG`; autenticación por llave u OAuth; roles de mínimo privilegio; `CLONE` de producción para desarrollo; `copy_grants` al recrear; DDL de producción solo por el pipeline | `*.p8`, `*.pem`, `connections.toml` |

El texto completo de cada capa está en [`profiles/<capa>/rules.es.md`](../profiles/) (y `.en.md`). **Son reglas base editables**: si tu equipo tiene otra convención, edita la sección «Perfil del proyecto» del `CLAUDE.md` y el agente la seguirá.

## Qué debería recordar la memoria en un proyecto de datos
Documentos recomendados en `docs/agent-memory/` (la skill `project-memory-bootstrap` los propone leyendo el repo):
- **Catálogo de modelos/tablas:** grain, partición y clustering, dueño, SLA, consumidores. Es lo que evita preguntar «¿esta tabla se refresca a diario?».
- **Fuentes y contratos:** de dónde viene cada fuente, su frecuencia y su calidad conocida.
- **Entornos:** nombres lógicos de proyectos/datasets/cuentas por entorno (nunca credenciales), `location` y roles.
- **Costos:** bytes procesados o créditos por ejecución típica (línea base) y regla de aprobación por umbral.
- **Decisiones:** por qué una tabla es incremental, por qué un backfill se hizo en ventanas, por qué se eligió una estrategia de partición.
- **Runbooks:** backfill seguro, reproceso de un día, rollback de una release, rotación de llaves.
- **Incidentes:** qué se rompió, causa y corrección (evita repetirlo).

## Despliegue en proyectos de datos
«Desplegado» **no** es «mergeado». Es el commit que efectivamente ejecutó o publicó el entorno:
- **Dataform:** el *release config* compiló ese commit y el *workflow config* de producción terminó bien.
- **dbt:** el job de producción (dbt Cloud, Airflow, CI/CD) terminó bien sobre ese commit.
- **Terraform/BigQuery:** `apply` correcto de ese commit.

Se registra solo tras verificarlo: `python3 -I <KIT>/scripts/memory_deploy.py record . prod --commit <sha> --note "job #123 OK"`. El briefing te dirá después cuántos commits faltan por ejecutar en `prod` y si tu rama está integrada y desplegada.

## Versiones y seguridad en datos
Se vigilan `dbt-core`, el adaptador (`dbt-snowflake`/`dbt-bigquery`), los paquetes de `packages.yml`, `@dataform/core` y el CLI de Dataform, y las dependencias Python/Node del repo. La auditoría OSV cubre PyPI y npm; los paquetes de dbt Hub **se inventarían pero OSV no los cubre**: revísalos a mano cuando cambien. Cuando subas una versión por seguridad, cita el CVE/GHSA en el mensaje del commit y quedará en el historial como `security`.

## OpenSpec en datos
Un cambio de OpenSpec en un proyecto de datos debería incluir en sus specs escenarios verificables: «**WHEN** llega una fila duplicada **THEN** el modelo conserva la más reciente por `id`», grain, tolerancia de frescura y tests/assertions que lo comprueban. El `design.md` es el lugar para costo estimado (bytes/créditos), estrategia incremental y plan de backfill. La memoria indexa esos specs: la próxima sesión sabe *por qué* el modelo se comporta así.

## Qué NO hace
No ejecuta `dbt`, `dataform`, `bq` ni `snowsql` por sí misma, no se conecta a tu warehouse y no lee datos reales. Las reglas guían al agente; las credenciales y la ejecución siguen siendo tuyas.
