#!/usr/bin/env python3
"""Startup briefing (deterministic, no LLM, no Cognee, ~1.5k tokens max).

Reads only Markdown + Git: objective, current decisions, business rules, open items,
deployments, branch checkpoint and latest handoff, and stale notes. It is injected at session start (SessionStart hook).
Usage: memory_brief.py <repo> [--max-chars 6000]
"""
import re, subprocess, sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
cap = int(sys.argv[sys.argv.index("--max-chars") + 1]) if "--max-chars" in sys.argv else 6000
mem = repo / "docs" / "agent-memory"
cfg = repo / ".agent-memory" / "project.yaml"
lang = "en"
if cfg.exists():
    m_ = re.search(r"^language:\s*(es|en)\b", cfg.read_text(encoding="utf-8"), re.M)
    lang = m_.group(1) if m_ else "en"
L = {
    "es": dict(head="Memoria del proyecto (briefing de arranque, sin consulta a Cognee)", goal="Objetivo", decs="Decisiones vigentes (detalle: docs/agent-memory/decisions/)",
               rules="Reglas de negocio (docs/agent-memory/business/)", pend="Pendientes abiertos", hand="Retomar: checkpoint de la rama actual", hand_real="Ultimo handoff real", obs="Notas posiblemente obsoletas (verifica antes de confiar)",
               cut="… [briefing recortado]",
               foot="\nEsto ya es contexto cargado: no lo vuelvas a consultar. Para historial mas profundo usa la skill project-memory-recall (CHUNKS, top_k 3) si el briefing no alcanza, antes de preguntar o asumir. Al cerrar un hito: project-memory-handoff."),
    "en": dict(head="Project memory (startup briefing, no Cognee query)", goal="Objective", decs="Current decisions (details: docs/agent-memory/decisions/)",
               rules="Business rules (docs/agent-memory/business/)", pend="Open items", hand="Resume: checkpoint of the current branch", hand_real="Latest real handoff", obs="Possibly stale notes (verify before trusting)",
               cut="… [briefing truncated]",
               foot="\nThis is already loaded context: do not query it again. For deeper history use the project-memory-recall skill (CHUNKS, top_k 3) when the briefing is not enough, before asking or assuming. When a milestone ends: project-memory-handoff."),
}[lang]
GOAL_NAMES = ("Objetivo", "Objective")


def read(p):
    return p.read_text(encoding="utf-8") if p.exists() else ""


def meta(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    d = {}
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln and not ln.startswith(" "):
                k, v = ln.split(":", 1); d[k.strip()] = v.strip()
    return d, (m.group(2) if m else text)


def section(body, title):
    m = re.search(rf"^## {re.escape(title)}[^\n]*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    return m.group(1).strip() if m else ""


def clip(s, n):
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


out = [f"# {L['head']}"]
_, body = meta(read(mem / "project.md"))
if body:
    out += ["", f"## {L['goal']}", clip(next((section(body, n) for n in GOAL_NAMES if section(body, n)), ""), 450)]

decs = []
for f in sorted((mem / "decisions").glob("*.md")):
    m, b = meta(read(f))
    if m.get("status") in ("verified", "draft"):
        title = re.search(r"^# (.+)$", b, re.M)
        dec = section(b, "Decision") or section(b, "Decisión") or section(b, "Decisao")
        decs.append(f"- [{m.get('status')}] {clip(title.group(1) if title else f.stem, 80)}: {clip(dec, 150)}")
if decs:
    out += ["", f"## {L['decs']}"] + decs

_, rb = meta(read(mem / "business" / "rules.md"))
def bullets(text):
    items, cur = [], None
    for l in text.splitlines():
        if l.startswith("- "):
            cur = l[2:]; items.append(cur)
        elif cur is not None and l.startswith("  ") and l.strip():
            items[-1] += " " + l.strip()
        else:
            cur = None
    return items


rules = [clip(x, 140) for x in bullets(rb)]
if rules:
    out += ["", f"## {L['rules']}"] + [f"- {r}" for r in rules[:9]]

pend = []
for f in sorted(mem.rglob("*.md")):
    if "_local" in f.parts or "handoffs" in f.parts or "security" in f.parts:  # the latest handoff is included separately, in full
        continue
    _, b = meta(read(f))
    pend += [f"- {clip(l[6:], 130)} ({f.relative_to(mem).as_posix()})" for l in b.splitlines() if l.startswith("- [ ] ")]
if pend:
    out += ["", f"## {L['pend']}"] + pend[:6]

# Deployments and status of the current branch relative to what is deployed (scripts/memory_deploy.py)
dep = subprocess.run([sys.executable, "-I", str(Path(__file__).parent / "memory_deploy.py"), "status", str(repo), "--lang", lang],
                     capture_output=True, text=True).stdout.splitlines()
if dep:
    out += [""] + [clip(l, 150) if i == 0 or not l.startswith(" ") else l[:150] for i, l in enumerate(dep)]

# Dependencies/security: records version changes (local, fast) and launches the OSV audit in the background if it is stale
here = Path(__file__).parent
if (repo / ".agent-memory" / "project.yaml").exists():
    subprocess.run([sys.executable, "-I", str(here / "memory_deps.py"), "snapshot", str(repo)], capture_output=True, timeout=15)
    aud = subprocess.run([sys.executable, "-I", str(here / "memory_audit.py"), "status", str(repo), "--lang", lang], capture_output=True, text=True).stdout.splitlines()
    try:  # does not block startup: detached process; without network it simply fails silently
        subprocess.Popen([sys.executable, "-I", str(here / "memory_audit.py"), "run", str(repo), "--max-age-hours", "24"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        pass
    if aud:
        out += [""] + [l[:160] for l in aud]

# Data projects: graph freshness + connection catalog. `data_sync.py hook` prints one line and, only if sources changed
# (or a live check is due), launches the incremental sync detached: nothing runs when nothing changed.
if (repo / ".agent-memory" / "project.yaml").exists():
    try:
        _dl = subprocess.run([sys.executable, "-I", str(here / "data_sync.py"), "--repo", str(repo), "hook"], capture_output=True, text=True, timeout=12).stdout.strip()
        _cl = subprocess.run([sys.executable, "-I", str(here / "data_connect.py"), "--repo", str(repo), "brief"], capture_output=True, text=True, timeout=8).stdout.strip()
        if _dl or _cl:
            out += ["", *[x[:420] for x in (_dl, _cl) if x]]
    except Exception:
        pass

# OpenSpec: active changes (proposals in progress) and number of current specs
osd = repo / "openspec"
if osd.is_dir():
    act = sorted(d.name for d in (osd / "changes").glob("*") if d.is_dir() and d.name != "archive") if (osd / "changes").is_dir() else []
    nspec = len([d for d in (osd / "specs").glob("*") if d.is_dir()]) if (osd / "specs").is_dir() else 0
    out += ["", f"OpenSpec: {nspec} spec(s) vigente(s); cambios activos: {', '.join(act) if act else 'ninguno'}" if lang == "es" else
            f"OpenSpec: {nspec} current spec(s); active changes: {', '.join(act) if act else 'none'}"]

# Git hygiene: uncommitted changes (and how many are memory-related) and drift of the main branch from origin (local refs, no network)
def _git(*a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()
_st = [l[3:] for l in _git("status", "--porcelain").splitlines() if l]
_mem = [f for f in _st if f.startswith(("docs/agent-memory", ".agent-memory", "openspec", "CLAUDE.md"))]
_main = (_git("symbolic-ref", "--short", "refs/remotes/origin/HEAD") or "origin/master").split("/", 1)[-1]
_ab = _git("rev-list", "--left-right", "--count", f"{_main}...origin/{_main}").split()
_ahead, _behind = (int(_ab[0]), int(_ab[1])) if len(_ab) == 2 else (0, 0)
if _st or _ahead or _behind:
    out += ["", (f"Git: {len(_st)} archivo(s) sin commit ({len(_mem)} de memoria/OpenSpec); {_main} local vs origin: +{_ahead}/-{_behind}. Regla: commit y rama principal al dia." if lang == "es" else
                 f"Git: {len(_st)} uncommitted file(s) ({len(_mem)} memory/OpenSpec); local {_main} vs origin: +{_ahead}/-{_behind}. Rule: commit and keep main up to date.")]

# Resume: automatic checkpoint of the CURRENT BRANCH (not the last one written on any branch) and the latest real handoff
branch = subprocess.run(["git", "-C", str(repo), "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
auto = mem / "handoffs" / "_local" / f"auto-{re.sub(r'[^A-Za-z0-9._-]', '_', branch or 'detached')}.md"
if auto.exists():
    keep = [l for l in read(auto).splitlines() if l.strip() and not l.startswith("(Generado") and not l.lstrip().startswith(("- ??", "- M ", "- A ", "- D "))
            and not re.match(r"\s+- [?MADR ]{1,2} \S", l)]
    out += ["", f"## {L['hand']} ({auto.relative_to(mem).as_posix()})"] + [clip(l, 170) for l in keep[:14]]
real = sorted((p for p in (mem / "handoffs").glob("*.md")), key=lambda p: p.stat().st_mtime, reverse=True)
if real:
    out += ["", f"## {L['hand_real']}: {real[0].relative_to(mem).as_posix()}"] + [clip(l, 170) for l in meta(read(real[0]))[1].splitlines()[:6] if l.strip()]

st = subprocess.run([sys.executable, "-I", str(Path(__file__).parent / "memory_stale.py"), str(repo)],
                    capture_output=True, text=True).stdout.splitlines()
obs = [l for l in st if l.startswith("STALE")]
if obs:
    out += ["", f"## {L['obs']}"] + [f"- {l}" for l in obs[:6]]

footer = L["foot"]
body = "\n".join(out)
if len(body) + len(footer) > cap:  # the cap truncates the body, never the footer
    body = body[: cap - len(footer) - 30].rstrip() + "\n" + L["cut"]
print(body + "\n" + footer)
