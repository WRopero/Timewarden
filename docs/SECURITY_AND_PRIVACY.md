# Seguridad y privacidad

## Qué sale de tu equipo
| Dato | Destino | Cuándo |
|---|---|---|
| Fragmentos de tus documentos de memoria | Claude (tu suscripción), vía el observer | Solo al **indexar** y al leer texto recuperado en la conversación |
| Nombres y versiones de paquetes | `api.osv.dev` | Auditoría de vulnerabilidades, máx. cada 24 h |
| Nada más | — | Embeddings, búsqueda, grafo, base de datos y panel son 100 % locales |

## Superficie de red
Todos los puertos se publican solo en `127.0.0.1` (45873–45876 y 8017). El panel añade validación de `Host` (anti DNS-rebinding), CSP estricta, `X-Frame-Options` y `no-store`, y no monta el socket de Docker: usa un proxy de solo lectura con lista blanca.

## Secretos
- Los secretos del stack se generan por equipo (modo 0600) y no se versionan; el `.env` del panel también.
- El rol de base de datos del panel (`mm_reader`) es de solo lectura, con límite de 15 s y una sola sentencia `SELECT/WITH/EXPLAIN/SHOW/VALUES/TABLE`.
- Los perfiles excluyen de la indexación `.env*`, `profiles.yml`, llaves, cuentas de servicio y estado de Terraform.
- Nunca guardes credenciales ni datos reales sensibles en los documentos de memoria.

## Prohibido (también para el agente)
`docker compose down -v`, `forget` con `everything`, montar el directorio del observer en un contenedor, publicar puertos fuera de `127.0.0.1`, ejecutar contra producción sin aprobación.

## Aislamiento entre proyectos
Cada proyecto tiene su propio dataset (`<id>-knowledge`, `<id>-sessions`) y por defecto `cross_project_recall: false`.

## Modelo de amenazas, en corto
Es una herramienta local de un solo usuario: protege contra fugas accidentales (puertos, secretos en memoria, SQL destructivo desde el panel), no contra un atacante con acceso a tu cuenta del equipo.
