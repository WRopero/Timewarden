# Prompt para pegar a un agente

Descomprime el kit en cualquier carpeta (la llamaremos `<KIT>`: contiene `seed-bundle/SEED.md`). Abre Claude Code y pega el bloque cambiando `<KIT>`, `<repo>` y `<project_id>`:

```text
Instala la memoria de proyecto en <repo> con project_id <project_id>.
El kit de instalación está en <KIT> (carpeta que contiene seed-bundle/SEED.md). Trabaja desde esa carpeta.
Lee seed-bundle/SEED.md y sigue las fases en orden con seed-bundle/seed.sh. Reglas:
- Pregunta antes de arrancar contenedores, instalar el plugin, levantar el panel o indexar (gasta tokens).
- Si el idioma (español/inglés) o el tipo de proyecto (dbt, Dataform, Snowflake, BigQuery, aplicación web, etc.) no es obvio, pregúntame; no lo adivines. Si el instalador sale con código 3, es una pregunta para mí.
- No imprimas secretos. Nada de `down -v` ni `forget everything`.
- Solo está validado macOS + Docker Desktop: si estoy en otro sistema, avísame antes de seguir.
- Al terminar, dame: qué instalaste, dónde, costo en tokens, cómo desconectarlo y los resultados de `seed.sh verify`.
```

Solo la infraestructura (sin proyecto) en un equipo nuevo: «Ejecuta las fases 1 a 3 de SEED.md». Otro repositorio después: repetir desde la fase 2 con otro `project_id`.
