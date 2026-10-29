## ADDED Requirements

### Requirement: Inventario de versiones
El sistema SHALL mantener, por proyecto, el inventario de las dependencias directas con la versión resuelta en los lockfiles (Poetry, npm, requirements fijados) y las versiones de runtime declaradas en Dockerfiles.

#### Scenario: Lockfile sin cambios
- **WHEN** se abre una sesión y los lockfiles no cambiaron
- **THEN** el inventario no se modifica y no se escriben archivos

### Requirement: Historial de cambios con motivo
Cuando cambie una versión, el sistema SHALL registrar fecha, paquete, versión anterior y nueva, commit y motivo (`security` si el último commit del lockfile menciona un CVE, GHSA o vulnerabilidad; `upgrade` en otro caso) y MUST permitir anotar cambios manualmente.

#### Scenario: Corrección de seguridad
- **WHEN** un commit sube `brotli` y su mensaje cita un CVE
- **THEN** el historial marca el cambio como `security` y guarda el identificador

### Requirement: Auditoría automática de vulnerabilidades
Al iniciar una sesión el sistema SHALL lanzar en segundo plano, como máximo una vez cada 24 horas, una auditoría contra una base pública de vulnerabilidades usando las versiones exactas de los lockfiles. El arranque MUST NOT esperar a la auditoría y, sin red, MUST fallar en silencio registrando el error.

#### Scenario: Auditoría reciente
- **WHEN** la última auditoría tiene menos de 24 horas
- **THEN** no se consulta la red

#### Scenario: Sin red
- **WHEN** no hay conexión
- **THEN** la sesión inicia con normalidad y el briefing indica que el último intento falló

### Requirement: Pendientes de seguridad visibles
El briefing de arranque SHALL mostrar el número de vulnerabilidades abiertas, cuántas son altas o críticas y las más graves con la versión que las corrige, y el sistema SHALL escribir la lista completa como casillas pendientes en un documento de memoria indexable. Se MUST poder aceptar un riesgo listando su identificador en un archivo de excepciones.

#### Scenario: Vulnerabilidad crítica en una dependencia directa
- **WHEN** la auditoría encuentra una vulnerabilidad crítica en un paquete directo
- **THEN** aparece primera en el briefing con la versión corregida

#### Scenario: Riesgo aceptado
- **WHEN** un identificador está en el archivo de excepciones
- **THEN** no se cuenta ni se lista
