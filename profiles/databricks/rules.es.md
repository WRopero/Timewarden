#### Capa Databricks
- **Nombres de tres partes** (`catalogo.esquema.tabla`, Unity Catalog). No fijes URLs de workspace, tokens ni IDs de cluster en el codigo: usa variables del bundle o el perfil del CLI del usuario.
- **El target define el entorno.** Trabaja con `databricks bundle validate|summary -t dev`; `bundle deploy -t prod` y ejecutar jobs/pipelines de produccion requieren aprobacion explicita.
- **Costo = computo.** Usa SQL warehouses serverless o job clusters dimensionados con auto-terminacion; no dejes clusters all-purpose encendidos.
- **Tablas Delta:** declara particionado/clustering a proposito, `OPTIMIZE`/`VACUUM` solo desde el pipeline, y revisa `DESCRIBE HISTORY` antes de cambios destructivos. Usa expectations de DLT para calidad.
- **Seguridad:** OAuth sobre tokens personales; secretos en secret scopes, nunca en notebooks; permisos minimos en catalogos/esquemas. `.databrickscfg` y tokens **nunca** van al repo ni a la memoria.
- **Linaje y conexion:** consulta el grafo del proyecto antes de preguntar como se relacionan los objetos y lee el catalogo de conexiones antes de preguntar como conectarse.
