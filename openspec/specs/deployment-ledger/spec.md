# deployment-ledger Specification

## Purpose
Registrar qué commit está desplegado por entorno y mostrar el estado de cada rama respecto a lo desplegado.

## Requirements

### Requirement: Registro de despliegues por entorno
El sistema SHALL guardar, por entorno, el commit desplegado, la fecha y una nota, y SHALL registrar un despliegue únicamente a petición explícita tras verificar su salud.

#### Scenario: Registro tras verificar
- **WHEN** el agente despliega y la comprobación de salud es correcta
- **THEN** ejecuta el registro con el commit desplegado

### Requirement: Estado por rama
El briefing SHALL indicar cuántos commits de la rama principal faltan por desplegar y, para la rama actual, si está integrada en la principal y si está desplegada.

#### Scenario: Rama abierta
- **WHEN** la rama actual tiene commits que no están en la principal
- **THEN** el briefing la marca como no integrada y sin desplegar

#### Scenario: Commit desconocido
- **WHEN** el commit registrado no existe en el clon local
- **THEN** el briefing avisa que debe verificarse
