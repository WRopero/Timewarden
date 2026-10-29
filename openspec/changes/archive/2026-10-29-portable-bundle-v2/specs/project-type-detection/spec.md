## ADDED Requirements

### Requirement: Detección del tipo de proyecto
El instalador SHALL inspeccionar el repositorio y proponer un perfil compuesto por una o dos capas entre `dbt`, `dataform`, `snowflake`, `bigquery`, `webapp`, `python-lib` y `generic` (p. ej. `dbt,snowflake`, `dataform,bigquery`), con un nivel de confianza entre 0 y 1 y la lista de evidencias (archivos que motivaron la decisión).

#### Scenario: Proyecto dbt claro
- **WHEN** el repositorio contiene `dbt_project.yml`
- **THEN** las capas propuestas son `dbt` y `snowflake` si el adaptador configurado es Snowflake (`dbt,bigquery` si es BigQuery), y la confianza es al menos 0,75

#### Scenario: Proyecto Dataform claro
- **WHEN** el repositorio contiene `workflow_settings.yaml` o `dataform.json` y archivos `.sqlx` bajo `definitions/`
- **THEN** las capas propuestas son `dataform` y `bigquery` con confianza al menos 0,75

### Requirement: Pregunta obligatoria cuando es ambiguo
Cuando la confianza sea menor que 0,75, existan evidencias de dos perfiles de datos a la vez, o el repositorio esté casi vacío, la detección MUST terminar con un código de salida distinto de cero reservado para "ambiguo" y el agente MUST preguntar al usuario antes de instalar. El instalador MUST NOT adivinar.

#### Scenario: dbt sin adaptador detectable
- **WHEN** existe `dbt_project.yml` y no hay evidencia del adaptador
- **THEN** el resultado es ambiguo y se pregunta qué warehouse usa (Snowflake, BigQuery u otro)

#### Scenario: Repositorio vacío
- **WHEN** el repositorio no contiene archivos reconocibles
- **THEN** el resultado es ambiguo y se ofrece elegir manualmente entre los perfiles disponibles

### Requirement: Elección explícita
El instalador SHALL aceptar el perfil como argumento explícito y registrarlo en el contrato del proyecto para que hooks y skills lo usen.

#### Scenario: Perfil forzado
- **WHEN** se instala con `--profile dataform-bigquery`
- **THEN** el contrato del proyecto registra ese perfil y no se ejecuta la detección automática
