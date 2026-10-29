# ambiguity-recall-rule Specification

## Purpose
Hacer que el agente consulte la memoria antes de decidir, asumir o preguntar cuando una tarea es ambigua.

## Requirements

### Requirement: Consultar antes de decidir
Las instrucciones que el instalador deja en el proyecto SHALL ordenar al agente que, ante un requisito poco claro, una decisión de diseño o un "por qué está así", consulte la memoria (incluidos los specs de OpenSpec) y verifique su frescura antes de decidir, asumir o preguntar.

#### Scenario: Requisito ambiguo
- **WHEN** el agente no puede resolver un requisito con el contexto cargado
- **THEN** consulta la memoria y solo pregunta al usuario si persiste la ambigüedad

### Requirement: Límite de costo
La consulta MUST usar recuperación por fragmentos (sin pasar por un modelo) y MUST NOT repetirse sobre lo que el briefing ya contiene.

#### Scenario: Dato ya en el briefing
- **WHEN** la respuesta está en el briefing de arranque
- **THEN** el agente no consulta la memoria
