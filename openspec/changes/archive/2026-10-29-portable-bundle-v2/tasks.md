## 1. Detección y perfiles
- [x] 1.1 `scripts/detect_project_type.py` con evidencias, confianza y salida 3 si es ambiguo
- [x] 1.2 `profiles/` con `dbt-snowflake`, `dataform-bigquery`, `bigquery-sql`, `webapp`, `generic` (es/en)
- [x] 1.3 Integrar `--profile` en `install_project.py` y `seed.sh project`; registrar `profile:` y `memory_system:` en el contrato
- [x] 1.4 Extender `memory_deps.py` a `packages.yml`/`dbt_project.yml`/`@dataform/core`

## 2. Memoria de seguridad, despliegues y OpenSpec
- [x] 2.1 Revisar `memory_deps.py`, `memory_audit.py`, `memory_deploy.py` y su integración en el briefing
- [x] 2.2 Regla de ambigüedad y de OpenSpec en las plantillas de `CLAUDE.md` y en la skill de recall
- [x] 2.3 Skill/rutas sin ubicaciones absolutas (usar `memory_system:` del contrato)

## 3. Portabilidad y empaquetado
- [x] 3.1 Quitar nombres de proyecto y cuentas del bundle, la spec y los textos
- [x] 3.2 Raíz relocalizable y panel incluido en el paquete
- [x] 3.3 `scripts/package_bundle.sh` con lista blanca y escaneo de neutralidad/secretos
- [x] 3.4 `LEEME` y guía para proyectos de datos (BigQuery/Dataform, Snowflake/dbt)

## 4. Verificación
- [x] 4.1 Descomprimir en un directorio temporal y correr `doctor`
- [x] 4.2 Instalar el contrato en repos de muestra dbt y Dataform y verificar detección y reglas
- [x] 4.3 `openspec validate portable-bundle-v2` y archivar el cambio
