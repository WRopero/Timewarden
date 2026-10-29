# SEED — runbook para que un agente instale la memoria de proyecto

Audiencia: un agente (Claude Code u otro) que debe instalar la memoria Cognee en **un equipo y un repositorio nuevos, sin conocer este sistema**. Sigue las fases en orden. Cada fase tiene un comando, un resultado esperado y qué hacer si falla. Detalle técnico: `spec/Cognee-memory-specification.md` §21. Todas las rutas son relativas a la carpeta del kit (`<KIT>`, la que contiene este archivo en `seed-bundle/`); no hay rutas fijas.

## Reglas del agente
1. **Pregunta antes de cambiar el sistema** (fases `machine`, plugin, panel, `index`): arrancan contenedores, tocan ajustes globales de Claude Code o gastan tokens.
2. **Pregunta el idioma y el tipo de proyecto si no son obvios** (fases 2 y 2b). Nunca los adivines: el instalador sale con código 3 para que preguntes.
3. No imprimas ni pegues secretos (`deploy/docker/.env`, `~/.cognee/.env`, token del observer, `profiles.yml`, cuentas de servicio).
4. Prohibido: `docker compose down -v`, `forget` con `everything`, montar `~/.cognee-plugin/observer/`, publicar puertos fuera de `127.0.0.1`.
5. Si algo falla, lee la tabla de troubleshooting (spec §21.7) antes de improvisar. Reporta lo que se probó y lo que **no** se probó.
6. Solo está validado macOS + Docker Desktop. En Linux/Windows avisa al usuario antes de seguir y reporta cada diferencia.

## Cómo funciona (para explicárselo al usuario en 30 segundos)
Todo corre **en el equipo del usuario**, en Docker: Cognee, PostgreSQL con pgvector, el MCP y el panel. Los **embeddings se calculan en local** (sin internet ni suscripción). La búsqueda es local y gratis. Lo único que sale a Claude es el texto que se **indexa** (resúmenes y conceptos, vía el *observer* con `claude -p`, gasta tokens de la suscripción) y el texto recuperado que Claude Code lee en la conversación. La auditoría de vulnerabilidades envía a `api.osv.dev` solo **nombres y versiones de paquetes**.

## Fase 0 — Entender el pedido
Confirma con el usuario: (a) un repositorio o varios, (b) `project_id` estable (minúsculas, guiones; no la ruta), (c) datos que **no** deben entrar (clientes, bancarios, secretos), (d) ¿la captura de sesiones queda encendida (con topes) o apagada (`--no-capture`)? Por defecto: encendida con topes.

## Fase 1 — Requisitos
```bash
cd <KIT> && seed-bundle/seed.sh doctor
```
Esperado: Docker corriendo, `claude` ≥ 2.1.287 con sesión iniciada, python3, git, **OpenSpec** (CLI `openspec`; es parte de la instalación — si falta, propón al usuario instalarlo con `curl -fsSL https://raw.githubusercontent.com/Fission-AI/OpenSpec/main/scripts/binary/install.sh | sh` tras enseñarle el script, o `npm i -g @fission-ai/openspec`), puertos 45873–45876 y 8017 libres (o ya usados por este stack). Si Docker no corre, pide abrirlo. El primer arranque descarga imágenes y ~640 MB del modelo de embeddings.

## Fase 2 — Idioma del proyecto (pregunta obligatoria si es ambiguo)
```bash
python3 -I scripts/detect_language.py <repo>     # LANG=es|en|unknown CONFIDENCE=0..1
```
Exit 0 (confianza ≥ 0,75): informa y continúa. Exit 2 / `unknown`: **pregunta** «¿El proyecto está en español o en inglés?» y pasa `--lang es|en`. El idioma decide plantillas, sección de `CLAUDE.md`, briefing y documentos.

## Fase 2b — Tipo de proyecto y perfil (pregunta obligatoria si es ambiguo)
```bash
python3 -I scripts/detect_project_type.py <repo>  # PROFILES=dbt,snowflake CONFIDENCE=.. EVIDENCE=.. [ASK=.. OPTIONS=a|b|c]
```
Un perfil son 1–2 **capas**: `dbt`, `dataform`, `snowflake`, `bigquery`, `webapp`, `python-lib`, `generic` (p. ej. `dbt,snowflake`, `dbt,bigquery`, `dataform,bigquery`, `bigquery`). Exit 0: informa lo detectado y su evidencia. Exit 2 (ASK/OPTIONS): **pregunta al usuario** con esas opciones (casos típicos: dbt sin adaptador detectable; repo vacío; evidencias de dos warehouses) y pasa `--profile <capas>`. Cada capa aporta reglas al `CLAUDE.md` del proyecto, exclusiones de indexación (credenciales, llaves, estado de Terraform) y plantillas. Para proyectos de datos lee `docs/DATA_PROJECTS.md`.

## Fase 3 — Máquina (una vez por equipo) — requiere aprobación
```bash
seed-bundle/seed.sh machine --yes
```
Arranca el observer, genera secretos (0600), levanta Postgres/API/MCP/collector, espera `/health` = `ready` (60–90 s o más la primera vez), crea las llaves del MCP y del plugin, crea `~/.cognee/.env` desde `config/plugin.example.env` si no existe (captura de sesiones encendida con topes) e instala el LaunchAgent del observer (macOS; reversible con `scripts/observer_launchagent.sh uninstall`; si el plugin aún no está instalado se reintenta tras la fase 4).

## Fase 4 — Proyecto (una vez por repo) — idioma, perfil y plugin requieren aprobación
```bash
seed-bundle/seed.sh project <repo> <project_id> --lang auto --profile auto [--no-capture] [--with-plugin]
```
Crea `.agent-memory/project.yaml` (contrato con idioma, perfil y exclusiones), `.agent-memory/local.yaml` (ruta del kit en este equipo, **no versionado**), el esqueleto `docs/agent-memory/`, la sección de memoria en `CLAUDE.md` (reglas del perfil, regla de consultar la memoria ante ambigüedad, despliegues, seguridad y OpenSpec), hooks (briefing/checkpoint) en `.claude/settings.local.json`, skills `project-memory-*` y exclusiones locales de Git. **Código de salida 3** = idioma o perfil ambiguo → vuelve a las fases 2/2b y pregunta. Inicializa **OpenSpec** en el repo (`openspec/`, skills y comandos `/opsx:*`) salvo `--no-openspec`; el código de salida 4 con `--openspec yes` indica que falta el CLI. Sin `--with-plugin` imprime los tres comandos de `claude plugin`/`claude mcp` que modifican ajustes globales: ejecútalos solo con permiso, desde el repo.

## Fase 5 — Corpus piloto
Usa la skill `project-memory-bootstrap` (ya instalada): lee la documentación real, redacta `project.md` y `architecture.md` en `draft` y propone 10–20 documentos (decisiones, implementaciones, reglas de negocio, runbooks **que no estén ya en `CLAUDE.md`**). Lista las lagunas en vez de rellenarlas; `status: verified` solo tras comprobar. Si el repo usa **OpenSpec**, sus specs y cambios ya están en las fuentes del contrato: no los copies a `docs/agent-memory/`.

## Fase 6 — Indexar — requiere aprobación (gasta tokens)
```bash
scripts/memctl.sh sync <repo>            # plan: qué cambiaría, 0 llamadas
scripts/memctl.sh sync <repo> --apply    # ≈ 2 llamadas a Claude por chunk (15 docs ≈ 74 llamadas, 6 min)
```
Avisa del costo antes. Esperado: todos `indexed`.

## Fase 7 — Panel de control (Management Memory) — requiere aprobación
```bash
seed-bundle/seed.sh panel --yes          # http://127.0.0.1:45876 — solo lectura
```
Va **dentro del kit** (`panel/`): no clona nada. Instala (macOS) el disparador launchd bajo demanda para «Medir el equipo ahora» (sin proceso residente), refresca `view/usage.jsonl`, corre `panel/scripts/setup.py` (crea su `.env` 0600 y el rol Postgres de solo lectura; no imprime secretos) y hace `docker compose up -d --build` (2 contenedores). Muestra salud, vectores, grafo, PostgreSQL, tokens/costo, uso de la memoria, recursos y tamaño por proyecto. Parar: `docker compose stop` en `panel/` (nunca `down -v`). Para medir tokens de Claude Code, abre sesiones con `scripts/claude-memory <project_id>`.

## Fase 8 — Verificar y entregar
```bash
seed-bundle/seed.sh verify <repo>
scripts/memctl.sh eval <repo>            # con evals/cases.<project_id>.jsonl (20 preguntas; ver evals/cases.example.jsonl)
```
Aceptación: API ready, observer alcanzable desde contenedor, panel en :45876, MCP conectado, briefing < 6000 caracteres, recuperación correcta en top-5. Cierra con la skill `project-memory-handoff`, commit de `docs/agent-memory/`, `.agent-memory/` (salvo `local.yaml`) y `CLAUDE.md` por el flujo normal del repo, y entrega: qué se instaló, dónde, qué costó (tokens), cómo desconectar (`claude plugin disable cognee-memory@cognee`, `claude mcp remove agents_cognee`) y la fecha de revisión de consumo (una semana: `scripts/weekly_report.py`).

## Qué recuerda el sistema una vez instalado (verifícalo en la primera sesión)
- **Briefing al abrir sesión:** objetivo, decisiones, reglas, pendientes, despliegues, seguridad, cambios activos de OpenSpec, checkpoint de la rama actual y último handoff.
- **Despliegues** (`scripts/memory_deploy.py record <repo> <entorno> --commit <sha>`): qué commit está desplegado por entorno y el estado de cada rama. Se registra **solo tras verificar**. En proyectos de datos "desplegado" = el job/release de producción terminó bien sobre ese commit.
- **Versiones y seguridad** (`memory_deps.py`, `memory_audit.py`): inventario de dependencias directas con historial (`security` si el commit cita un CVE/GHSA), auditoría OSV lanzada sola al abrir sesión (máx. cada 24 h, en segundo plano, sin red falla en silencio) y pendientes en `docs/agent-memory/security/dependencias.md`. Aceptar un riesgo: `.agent-memory/security-ignore.txt`. Registrar a mano un cambio previo: `memory_deps.py note <repo> --pkg X --reason security --cve CVE-... --date AAAA-MM-DD`.
- **OpenSpec dirige toda implementación o cambio** (regla obligatoria en `CLAUDE.md`): `/opsx:propose` → revisión del usuario → `/opsx:apply` → `/opsx:archive`; sin cambio activo no se escribe código de producto (excepciones: erratas, formato, hotfix urgente documentado después). Sus specs (vigentes) y cambios (activos y archivados) se indexan con `memctl.sh sync` y el briefing lista los activos.
- **Ante ambigüedad el agente consulta la memoria antes de decidir o preguntar** (regla en `CLAUDE.md`).

## Desinstalar un proyecto
Desconecta plugin y MCP (arriba), borra `.agent-memory/`, `docs/agent-memory/` (si el usuario quiere), la sección de `CLAUDE.md` y los hooks de `.claude/settings.local.json`. Los datos de Cognee de ese proyecto se eliminan con `forget` **del dataset concreto** (nunca `everything`).
