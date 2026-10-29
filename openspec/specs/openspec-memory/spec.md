# openspec-memory Specification

## Purpose
Integrar OpenSpec en la instalación como director obligatorio de los cambios y como parte indexada de la memoria del proyecto.

## Requirements

### Requirement: Specs y cambios como memoria
Si el repositorio usa OpenSpec, el sistema SHALL indexar `openspec/specs` como conocimiento vigente y `openspec/changes` (activos y archivados) como propuestas y su historial, sin exigir frontmatter.

#### Scenario: Spec vigente
- **WHEN** existe un archivo en `openspec/specs/<capacidad>/spec.md`
- **THEN** se indexa como tipo `openspec-spec` con estado `verified`

#### Scenario: Cambio activo
- **WHEN** existe un cambio no archivado
- **THEN** se indexa con estado `draft`

### Requirement: Resumen en el briefing
El briefing SHALL listar el número de specs vigentes y los nombres de los cambios activos.

#### Scenario: Sin cambios activos
- **WHEN** no hay cambios activos
- **THEN** el briefing lo indica explícitamente

### Requirement: OpenSpec forma parte de la instalación
El instalador SHALL comprobar la presencia del CLI de OpenSpec, inicializarlo en el repositorio del proyecto (con el idioma del proyecto) salvo que el usuario lo rechace, y informar con un código de salida específico si el CLI falta cuando se exige.

#### Scenario: CLI presente
- **WHEN** se instala la memoria en un repositorio sin `openspec/` y el CLI está disponible
- **THEN** el repositorio queda con OpenSpec inicializado y los comandos de flujo disponibles

#### Scenario: CLI ausente y exigido
- **WHEN** el CLI no está instalado y se exige OpenSpec
- **THEN** la instalación termina con el código de salida reservado para "falta OpenSpec" y explica cómo instalarlo

### Requirement: OpenSpec dirige todo cambio
Las instrucciones que deja el instalador SHALL establecer que cualquier funcionalidad nueva, cambio de comportamiento, refactor no trivial o cambio de datos/infraestructura se realiza mediante un cambio de OpenSpec (proponer, revisión del usuario, implementar, archivar), con excepciones limitadas a erratas, formato, comentarios y hotfix urgente documentado después.

#### Scenario: Petición de una funcionalidad
- **WHEN** el usuario pide una funcionalidad nueva
- **THEN** el agente crea una propuesta de cambio y espera la revisión antes de escribir código de producto

#### Scenario: Errata
- **WHEN** el cambio es una errata de texto
- **THEN** el agente lo aplica sin crear un cambio
