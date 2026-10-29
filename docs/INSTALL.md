# Cómo instalar OpenMemory

Hay dos caminos: **con un agente** (recomendado: él detecta el idioma y el tipo de proyecto y te pregunta lo ambiguo) o **a mano**. En ambos casos la instalación tiene dos niveles: **una vez por equipo** (el stack) y **una vez por repositorio** (el contrato, los hooks, las skills y OpenSpec).

## 0. Requisitos
| Necesitas | Cómo comprobarlo |
|---|---|
| macOS con Docker Desktop abierto (única plataforma validada) | `docker info` |
| Claude Code ≥ 2.1.287 con sesión iniciada | `claude --version` |
| Python 3 y git | `python3 --version`, `git --version` |
| OpenSpec (CLI) | `openspec --version`. Si falta: `curl -fsSL https://raw.githubusercontent.com/Fission-AI/OpenSpec/main/scripts/binary/install.sh \| sh` (revisa el script antes de ejecutarlo) o `npm i -g @fission-ai/openspec` |
| ~10 GB libres y internet la primera vez | Imágenes Docker y modelo de embeddings (~640 MB) |
`seed-bundle/seed.sh doctor` comprueba todo esto y no cambia nada.

## 1. Obtener el kit
```bash
git clone https://github.com/<tu-usuario>/OpenMemory.git      # o descomprime el .zip del release
cd OpenMemory
```
Puede vivir en **cualquier carpeta**: las rutas se resuelven desde su ubicación y cada repo guarda la suya en `.agent-memory/local.yaml` (no versionado).

## 2. Camino A — con un agente (recomendado)
Abre Claude Code y pega el bloque de [`seed-bundle/AGENT_PROMPT.md`](../seed-bundle/AGENT_PROMPT.md) cambiando `<KIT>`, `<repo>` y `<project_id>`. El agente sigue [`seed-bundle/SEED.md`](../seed-bundle/SEED.md): pregunta antes de arrancar contenedores, instalar el plugin, levantar el panel o indexar, y **te pregunta el idioma y el tipo de proyecto si no son obvios**.

## 3. Camino B — a mano
```bash
# 3.1 Una vez por equipo
seed-bundle/seed.sh doctor                    # requisitos
seed-bundle/seed.sh machine --yes             # observer + Docker + llaves + ~/.cognee/.env + LaunchAgent del observer

# 3.2 Una vez por repositorio
seed-bundle/seed.sh project /ruta/al/repo mi-proyecto --lang auto --profile auto --with-plugin
#   --lang auto      detecta es/en; si es ambiguo sale con código 3 -> usa --lang es|en
#   --profile auto   detecta el tipo (dbt, dataform, snowflake, bigquery, webapp...); ambiguo -> código 3 -> usa --profile dbt,snowflake
#   --no-openspec    omite OpenSpec (no recomendado: es parte del método)
#   --no-capture     no captura sesiones (solo briefing y recuperación)
#   --with-plugin    instala el plugin y el MCP en el ámbito del repo (si no, imprime los comandos)

# 3.3 Corpus inicial: en Claude Code, dentro del repo, pide usar la skill project-memory-bootstrap
#     (lee la documentación real y propone 10-20 documentos; revisa y marca verified solo lo comprobado)

# 3.4 Indexar (gasta tokens de tu suscripción: ~2 llamadas por fragmento)
scripts/memctl.sh sync /ruta/al/repo              # plan: 0 llamadas
scripts/memctl.sh sync /ruta/al/repo --apply

# 3.5 Panel y verificación
seed-bundle/seed.sh panel --yes                   # http://127.0.0.1:45876
seed-bundle/seed.sh verify /ruta/al/repo
```

### Códigos de salida que debes conocer
| Código | Significado | Qué hacer |
|---|---|---|
| 3 | Idioma o tipo de proyecto ambiguo | Responder la pregunta y repetir con `--lang` / `--profile` |
| 4 | Falta el CLI `openspec` con `--openspec yes` | Instalar OpenSpec |
| ≠ 0 en `doctor` | Falta un requisito | Leer la línea `FALTA` |

## 4. Qué debes ver al terminar
- `seed.sh verify` en verde: API lista, observer autenticado y alcanzable desde un contenedor, panel en :45876, contrato del proyecto, briefing ≤ 6000 caracteres, MCP `agents_cognee` conectado.
- Al abrir una sesión nueva en el repo, el briefing aparece solo (objetivo, decisiones, despliegues, seguridad, cambios de OpenSpec, checkpoint de la rama).
- `scripts/memctl.sh eval <repo>` con 20 preguntas (ver [`evals/README.md`](../evals/README.md)): objetivo ≥ 85 % de recall@5.

## 5. Más proyectos, otro equipo, actualizar, desinstalar
- **Otro repositorio:** repite solo el paso 3.2 (y 3.3–3.5) con otro `project_id`. El stack se comparte.
- **Otro equipo (otra PC):** clona o descomprime el kit allí y repite todo. **Los datos de la memoria no viajan:** viven en Docker en cada equipo. Lo que se comparte entre personas es el Markdown versionado en el repo (`docs/agent-memory/`, `openspec/`, `.agent-memory/`); cada quien ejecuta `memctl.sh sync <repo> --apply` y reconstruye su índice.
- **Actualizar el kit:** `git pull` (o el nuevo `.zip`) y `seed.sh verify`. Las versiones de las imágenes están fijadas en `config/versions.lock`; cambiar el modelo de embeddings obliga a reindexar.
- **Parar / pausar:** `scripts/memctl.sh stop` (nunca `docker compose down -v`); capturar menos: `COGNEE_CAPTURE=false` en `~/.cognee/.env`.
- **Desconectar un repo:** `claude plugin disable cognee-memory@cognee` y `claude mcp remove agents_cognee`; borra `.agent-memory/`, la sección de `CLAUDE.md` y los hooks de `.claude/settings.local.json`.

## 6. Problemas frecuentes
| Síntoma | Causa probable | Arreglo |
|---|---|---|
| `doctor`: Docker no corre | Docker Desktop cerrado | Abrirlo |
| La API no llega a `ready` | Primera descarga del modelo (60–90 s o más) | Esperar; `docker logs agents_cognee_api` |
| `observer no alcanzable desde Docker` | Observer caído o token | `scripts/observer.sh start` y `probe` |
| Tras reiniciar el equipo nada responde | Observer sin LaunchAgent | `scripts/observer_launchagent.sh install` |
| `recall` devuelve 404 | Nombre de dataset incorrecto | Copiar `memory_dataset` literal de `project.yaml` (string, no lista) |
| El agente no ve el briefing | Hooks no instalados o proyecto sin `.agent-memory/project.yaml` | Rehacer el paso 3.2 y abrir una sesión nueva |
| Puerto en uso | Otro servicio en 45873–45876 / 8017 | Liberarlo; el kit solo publica en `127.0.0.1` |
La tabla completa de resolución de problemas está en [`seed-bundle/spec/Cognee-memory-specification.md`](../seed-bundle/spec/Cognee-memory-specification.md) §21.7.
