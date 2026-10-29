#!/usr/bin/env python3
"""Instala la memoria en un repositorio: contrato, plantillas, skills, hooks y seccion de CLAUDE.md.

Uso: install_project.py <repo> --project-id <id> [--lang auto|es|en] [--profile auto|<capas>] [--no-capture]
OpenSpec: --openspec auto|yes|no (auto = lo inicializa si el CLI `openspec` esta instalado; yes = exige el CLI, codigo 4 si falta).
Perfil = 1 o 2 capas separadas por coma (dbt, dataform, snowflake, bigquery, webapp, python-lib, generic).
Con --profile auto detecta el tipo de proyecto y, si es ambiguo, pregunta (sin TTY sale con codigo 3).
Idempotente: no sobrescribe archivos existentes; fusiona (no pisa) .claude/settings.local.json.
No toca Docker ni el plugin: ver docs/operations.md y la guia de replica (spec 21).
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("repo", type=Path); ap.add_argument("--project-id", required=True)
ap.add_argument("--no-capture", action="store_true")
ap.add_argument("--lang", choices=("auto", "es", "en"), default="auto",
                help="idioma de los documentos de memoria; auto = detectar y, si es ambiguo, preguntar")
ap.add_argument("--openspec", choices=("auto", "yes", "no"), default="auto", help="inicializar OpenSpec en el repo (auto = si el CLI esta instalado)")
ap.add_argument("--profile", default="auto", help="auto o capas separadas por coma, p. ej. dbt,snowflake | dataform,bigquery | webapp")
a = ap.parse_args()
repo, pid = a.repo.resolve(), a.project_id
if not (repo / ".git").exists():
    sys.exit(f"{repo} no es un repositorio git")


def choose_lang():
    """es|en. Con --lang explicito no pregunta; en auto detecta y, si es ambiguo, pregunta (sin TTY aborta con codigo 3)."""
    if a.lang != "auto":
        return a.lang
    r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/detect_language.py"), str(repo)], capture_output=True, text=True)
    print(f"  idioma detectado: {r.stdout.strip()}")
    kv = dict(x.split("=") for x in r.stdout.split())
    if r.returncode == 0:
        return kv["LANG"]
    if sys.stdin.isatty():
        ans = input("  No se pudo determinar el idioma. ¿El proyecto está en español o en inglés? [es/en]: ").strip().lower()
        if ans in ("es", "en"):
            return ans
    print("IDIOMA_AMBIGUO: pregunta al usuario si el proyecto esta en espanol o ingles y reintenta con --lang es|en", file=sys.stderr)
    sys.exit(3)


PROFILES_DIR = ROOT / "profiles"
KNOWN = sorted(p.name for p in PROFILES_DIR.iterdir() if (p / "profile.yaml").exists())


def choose_profiles():
    """Lista de capas. Explicito: se valida. Auto: detecta; si es ambiguo pregunta (sin TTY: codigo 3 con las opciones)."""
    if a.profile != "auto":
        layers = [x.strip() for x in a.profile.split(",") if x.strip()]
        bad = [x for x in layers if x not in KNOWN]
        if bad:
            sys.exit(f"perfil desconocido: {bad}. Disponibles: {', '.join(KNOWN)}")
        return layers
    r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/detect_project_type.py"), str(repo)], capture_output=True, text=True)
    print(f"  tipo de proyecto: {r.stdout.strip()}")
    kv = dict(re.findall(r"([A-Z]+)=(.*?)(?= [A-Z]+=|$)", r.stdout.strip()))
    if r.returncode == 0:
        return kv["PROFILES"].split(",")
    opts = kv.get("OPTIONS", "generic").split("|")
    if sys.stdin.isatty():
        print(f"  {kv.get('ASK', 'Tipo de proyecto ambiguo')}")
        for i, o in enumerate(opts, 1):
            print(f"    {i}) {o}")
        ans = input("  Elige numero o escribe las capas separadas por coma: ").strip()
        pick = opts[int(ans) - 1] if ans.isdigit() and 0 < int(ans) <= len(opts) else ans
        if all(x in KNOWN for x in pick.split(",")):
            return pick.split(",")
    print(f"PERFIL_AMBIGUO: {kv.get('ASK', '')} Pregunta al usuario y reintenta con --profile <capas>. Opciones: {'  |  '.join(opts)}", file=sys.stderr)
    sys.exit(3)


lang = choose_lang()
layers = choose_profiles()
print(f"  perfil: {', '.join(layers)}")
T = ROOT / "templates" / lang
sub = lambda t: t.replace("__PROJECT_ID__", pid).replace("__MEMORY_SYSTEM__", str(ROOT)).replace("__LANG__", lang)
print(f"  idioma de la memoria: {lang}")


def put(dest: Path, text: str):
    if dest.exists():
        print(f"  existe, se respeta: {dest.relative_to(repo)}"); return
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(text, encoding="utf-8")
    print(f"  creado: {dest.relative_to(repo)}")


cfg = sub((ROOT / "templates/project.yaml.tmpl").read_text())
if a.no_capture:
    cfg = cfg.replace("capture_raw_sessions: true", "capture_raw_sessions: false")
prof_meta = [yaml_lines for yaml_lines in (((PROFILES_DIR / l / "profile.yaml").read_text()) for l in layers)]
extra_ex = []
for t in prof_meta:
    m = re.search(r"^exclude:\s*\[(.*)\]\s*$", t, re.M)
    extra_ex += [x.strip() for x in m.group(1).split(",")] if m else []
extra_ex = [e for e in dict.fromkeys(extra_ex) if e.strip("'\"") not in cfg]
cfg = cfg.replace("exclude:\n", "exclude:\n" + "".join(f"  - {e}\n" for e in extra_ex), 1)
cfg = cfg.replace("memory_dataset:", f"profile: {','.join(layers)}                 # capas de perfil (profiles/): reglas y exclusiones\nmemory_dataset:", 1)
put(repo / ".agent-memory/project.yaml", cfg)
# ruta del sistema de memoria: LOCAL a la maquina (no se versiona); skills y reglas la referencian como <MS>
loc = repo / ".agent-memory/local.yaml"
loc.write_text(f"# local a esta maquina; no se versiona\nmemory_system: {ROOT}\n", encoding="utf-8")
print("  creado/actualizado: .agent-memory/local.yaml (ruta del sistema, no versionado)")
mem = repo / "docs/agent-memory"
for d in ("business", "decisions", "implementations", "runbooks", "handoffs"):
    (mem / d).mkdir(parents=True, exist_ok=True)
put(mem / "project.md", sub((T / "project.md").read_text()))
for t in ("decision", "implementation", "handoff"):  # plantillas de referencia, fuera del indice
    put(repo / ".agent-memory/templates" / f"{t}.md", sub((T / f"{t}.md").read_text()))

claude = repo / "CLAUDE.md"
section = sub((T / "CLAUDE.memory-section.md").read_text())
prof_rules = [(PROFILES_DIR / l / f"rules.{lang}.md").read_text().strip() for l in layers if (PROFILES_DIR / l / f"rules.{lang}.md").exists() and l != "generic"]
if prof_rules:
    section = section.rstrip("\n") + ("\n\n### Perfil del proyecto\n\n" if lang == "es" else "\n\n### Project profile\n\n") + "\n\n".join(sub(r) for r in prof_rules) + "\n"
if claude.exists() and any(h in claude.read_text() for h in ("## Memoria del proyecto (Cognee)", "## Project memory (Cognee)")):
    print("  CLAUDE.md ya tiene la seccion de memoria")
else:
    claude.write_text((claude.read_text() if claude.exists() else "# CLAUDE.md\n") + section, encoding="utf-8")
    print("  CLAUDE.md: seccion de memoria anadida")

sp = repo / ".claude/settings.local.json"
settings = json.loads(sp.read_text()) if sp.exists() else {}
S = ROOT / "scripts"
hooks = settings.setdefault("hooks", {})
want = {
    "SessionStart": ('startup|resume|clear|compact', f'python3 -I {S}/memory_brief.py "$CLAUDE_PROJECT_DIR" 2>/dev/null || true'),
    "PreCompact": (None, f"python3 -I {S}/memory_checkpoint.py 2>/dev/null || true"),
    "SessionEnd": (None, f"python3 -I {S}/memory_checkpoint.py 2>/dev/null || true"),
}
for ev, (matcher, cmd) in want.items():
    if any("memory_brief.py" in h.get("command", "") or "memory_checkpoint.py" in h.get("command", "")
           for g in hooks.get(ev, []) for h in g.get("hooks", [])):
        continue
    group = {"hooks": [{"type": "command", "timeout": 20, "command": cmd}]}
    if matcher: group["matcher"] = matcher
    hooks.setdefault(ev, []).append(group)
sp.parent.mkdir(parents=True, exist_ok=True); sp.write_text(json.dumps(settings, indent=2, ensure_ascii=False))
print("  hooks SessionStart/PreCompact/SessionEnd en .claude/settings.local.json (archivo local, no se versiona)")

subprocess.run([str(S / "install_skills.sh"), str(repo)], check=True)

# OpenSpec: forma parte de la instalacion (dirige las implementaciones; ver la regla en CLAUDE.md)
import shutil
if a.openspec != "no":
    if (repo / "openspec").is_dir():
        print("  OpenSpec ya inicializado en el repo")
    elif shutil.which("openspec"):
        r = subprocess.run(["openspec", "init", "--tools", "claude", "--language", lang, "--no-animation", str(repo)], capture_output=True, text=True)
        print("  OpenSpec inicializado (openspec/, skills y comandos /opsx:* en .claude/)" if r.returncode == 0 else f"  OpenSpec init fallo: {(r.stdout + r.stderr)[-200:]}")
    else:
        msg = "OPENSPEC_FALTA: instala el CLI (ver SEED.md, requisitos) y ejecuta `openspec init --tools claude --language " + lang + "` en el repo."
        print("  " + msg, file=sys.stderr)
        if a.openspec == "yes":
            sys.exit(4)
ex = repo / ".git/info/exclude"
for line in ("docs/agent-memory/handoffs/_local/", ".agent-memory/local.yaml"):
    if line not in ex.read_text():
        ex.write_text(ex.read_text().rstrip("\n") + "\n" + line + "\n")
print(f"\nListo. Siguiente: escribir docs/agent-memory/project.md y los primeros documentos, luego\n"
      f"  {S}/memctl.sh sync {repo} --apply\n  (stack arriba y plugin/MCP configurados: ver spec 21)")
