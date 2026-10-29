# portable-bundle Specification

## Purpose
Distribuir el kit como un paquete neutral, relocalizable y autocontenido que otro agente pueda instalar en otro equipo.

## Requirements

### Requirement: Neutralidad
El paquete distribuible MUST NOT contener nombres de proyectos, empresas, cuentas, correos ni rutas absolutas de la máquina de origen, ni secretos, llaves, tokens, bases de datos ni evaluaciones de un proyecto concreto.

#### Scenario: Escaneo del paquete
- **WHEN** se empaqueta el bundle
- **THEN** un escaneo de términos prohibidos y patrones de secretos sobre todos los archivos del `.zip` no encuentra coincidencias, y el empaquetado falla si las hay

### Requirement: Relocalizable y autocontenido
El paquete SHALL poder instalarse en cualquier directorio, resolver todas las rutas relativas a su propia ubicación (con una variable para sobrescribirla) e incluir el panel Management Memory, de modo que no dependa de repositorios ni cuentas externas.

#### Scenario: Instalación en otro directorio
- **WHEN** se descomprime el `.zip` en un directorio arbitrario y se ejecuta la comprobación de requisitos
- **THEN** la comprobación reporta rutas correctas y no referencia ubicaciones del equipo de origen

### Requirement: Runbook y verificación
El paquete SHALL incluir el runbook por fases con puntos de aprobación, el prompt para pegar a un agente, la especificación técnica y una verificación de aceptación, y MUST documentar qué sale del equipo del usuario (solo el texto que se indexa vía Claude).

#### Scenario: Entrega
- **WHEN** un compañero recibe el `.zip`
- **THEN** encuentra un `LEEME` con los pasos mínimos y el prompt listo, sin conocer el sistema
