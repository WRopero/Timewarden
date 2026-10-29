## ADDED Requirements

### Requirement: Reglas de memoria para proyectos de datos
Cada perfil de datos SHALL aportar al agente reglas operativas que se inyectan en la sección de memoria del `CLAUDE.md` del proyecto y plantillas de documentos de memoria específicas (modelos, fuentes, linaje, entornos, costos).

#### Scenario: Perfil Dataform sobre BigQuery
- **WHEN** el proyecto usa las capas `dataform` y `bigquery`
- **THEN** las reglas incluyen estimar bytes procesados antes de ejecutar consultas costosas (dry run), exigir particionado y clustering en tablas grandes, no ejecutar ni reprogramar workflows de producción sin aprobación, y distinguir entornos por proyecto y dataset

#### Scenario: Perfil dbt sobre Snowflake
- **WHEN** el proyecto usa las capas `dbt` y `snowflake`
- **THEN** las reglas incluyen respetar los targets (`dev`/`prod`), no ejecutar `dbt run` ni `dbt build` contra `prod` sin aprobación, declarar tests y documentación en cada modelo, y vigilar el costo de warehouse (tamaño y auto-suspensión)

### Requirement: Seguridad de credenciales en proyectos de datos
Los perfiles MUST prohibir guardar credenciales, cuentas de servicio, llaves privadas o contenido de `profiles.yml` en la memoria, y MUST excluir de la indexación archivos de credenciales y salidas con datos reales.

#### Scenario: Archivos excluidos
- **WHEN** se instala un perfil de datos
- **THEN** el contrato del proyecto excluye `profiles.yml`, `*.json` de cuentas de servicio, `.env*` y directorios de datos de muestra

### Requirement: Versiones de herramientas de datos como dependencias vigiladas
El registro de dependencias SHALL incluir las versiones de dbt (paquetes de `packages.yml` y adaptadores), `@dataform/core` y del CLI cuando existan, de modo que los cambios por seguridad queden registrados.

#### Scenario: Cambio de versión de dbt
- **WHEN** cambia la versión fijada de un adaptador o paquete de dbt
- **THEN** el historial registra la fecha, versión anterior y nueva, y si el commit menciona una vulnerabilidad se marca como `security`

### Requirement: Despliegue en proyectos de datos
Para proyectos de datos, "desplegado" SHALL entenderse como el commit efectivamente ejecutado o publicado en el entorno (configuración de release de Dataform o job de producción de dbt), y solo se registra tras verificar su ejecución.

#### Scenario: Registro tras una ejecución de producción
- **WHEN** el job de producción termina correctamente para un commit
- **THEN** el agente registra ese commit en el entorno `prod` del registro de despliegues
