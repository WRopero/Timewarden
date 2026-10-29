#!/usr/bin/env python3
"""Installs the memory into a repository: contract, templates, skills, hooks and the CLAUDE.md section.

Usage: install_project.py <repo> --project-id <id> [--lang auto|es|en] [--profile auto|<layers>] [--no-capture]
OpenSpec: --openspec auto|yes|no (auto = initializes it if the `openspec` CLI is installed; yes = requires the CLI, code 4 if missing).
Profile = 1 or 2 comma-separated layers (dbt, dataform, snowflake, bigquery, webapp, python-lib, generic).
With --profile auto it detects the project type and, if ambiguous, asks (without a TTY it exits with code 3).
Idempotent: does not overwrite existing files; merges (does not clobber) .claude/settings.local.json.
Does not touch Docker or the plugin: see docs/operations.md and the replica guide (spec 21).
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("repo", type=Path); ap.add_argument("--project-id", required=True)
ap.add_argument("--no-capture", action="store_true")
ap.add_argument("--lang", choices=("auto", "es", "en"), default="auto",
                help="language of the memory documents; auto = detect and, if ambiguous, ask")
ap.add_argument("--openspec", choices=("auto", "yes", "no"), default="auto", help="initialize OpenSpec in the repo (auto = if the CLI is installed)")
ap.add_argument("--profile", default="auto", help="auto or comma-separated layers, e.g. dbt,snowflake | dataform,bigquery | webapp")
a = ap.parse_args()
repo, pid = a.repo.resolve(), a.project_id
if not (repo / ".git").exists():
    sys.exit(f"{repo} is not a git repository")


def choose_lang():
    """es|en. With an explicit --lang it does not ask; in auto it detects and, if ambiguous, asks (without a TTY it aborts with code 3)."""
    if a.lang != "auto":
        return a.lang
    r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/detect_language.py"), str(repo)], capture_output=True, text=True)
    print(f"  detected language: {r.stdout.strip()}")
    kv = dict(x.split("=") for x in r.stdout.split())
    if r.returncode == 0:
        return kv["LANG"]
    if sys.stdin.isatty():
        ans = input("  Could not determine the language. Is the project in Spanish or English? [es/en]: ").strip().lower()
        if ans in ("es", "en"):
            return ans
    print("AMBIGUOUS_LANGUAGE: ask the user whether the project is in Spanish or English and retry with --lang es|en", file=sys.stderr)
    sys.exit(3)


PROFILES_DIR = ROOT / "profiles"
KNOWN = sorted(p.name for p in PROFILES_DIR.iterdir() if (p / "profile.yaml").exists())


def choose_profiles():
    """List of layers. Explicit: it is validated. Auto: detects; if ambiguous it asks (without a TTY: code 3 with the options)."""
    if a.profile != "auto":
        layers = [x.strip() for x in a.profile.split(",") if x.strip()]
        bad = [x for x in layers if x not in KNOWN]
        if bad:
            sys.exit(f"unknown profile: {bad}. Available: {', '.join(KNOWN)}")
        return layers
    r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/detect_project_type.py"), str(repo)], capture_output=True, text=True)
    print(f"  project type: {r.stdout.strip()}")
    kv = dict(re.findall(r"([A-Z]+)=(.*?)(?= [A-Z]+=|$)", r.stdout.strip()))
    if r.returncode == 0:
        return kv["PROFILES"].split(",")
    opts = kv.get("OPTIONS", "generic").split("|")
    if sys.stdin.isatty():
        print(f"  {kv.get('ASK', 'Ambiguous project type')}")
        for i, o in enumerate(opts, 1):
            print(f"    {i}) {o}")
        ans = input("  Choose a number or type the layers separated by commas: ").strip()
        pick = opts[int(ans) - 1] if ans.isdigit() and 0 < int(ans) <= len(opts) else ans
        if all(x in KNOWN for x in pick.split(",")):
            return pick.split(",")
    print(f"AMBIGUOUS_PROFILE: {kv.get('ASK', '')} Ask the user and retry with --profile <layers>. Options: {'  |  '.join(opts)}", file=sys.stderr)
    sys.exit(3)


lang = choose_lang()
layers = choose_profiles()
print(f"  profile: {', '.join(layers)}")
T = ROOT / "templates" / lang
sub = lambda t: t.replace("__PROJECT_ID__", pid).replace("__MEMORY_SYSTEM__", str(ROOT)).replace("__LANG__", lang)
print(f"  memory language: {lang}")


def put(dest: Path, text: str):
    if dest.exists():
        print(f"  exists, left untouched: {dest.relative_to(repo)}"); return
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(text, encoding="utf-8")
    print(f"  created: {dest.relative_to(repo)}")


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
cfg = cfg.replace("memory_dataset:", f"profile: {','.join(layers)}                 # profile layers (profiles/): rules and exclusions\nmemory_dataset:", 1)
put(repo / ".agent-memory/project.yaml", cfg)
# path of the memory system: LOCAL to the machine (not versioned); skills and rules reference it as <MS>
loc = repo / ".agent-memory/local.yaml"
loc.write_text(f"# local to this machine; not versioned\nmemory_system: {ROOT}\n", encoding="utf-8")
print("  created/updated: .agent-memory/local.yaml (system path, not versioned)")
mem = repo / "docs/agent-memory"
for d in ("business", "decisions", "implementations", "runbooks", "handoffs"):
    (mem / d).mkdir(parents=True, exist_ok=True)
put(mem / "project.md", sub((T / "project.md").read_text()))
for t in ("decision", "implementation", "handoff"):  # reference templates, outside the index
    put(repo / ".agent-memory/templates" / f"{t}.md", sub((T / f"{t}.md").read_text()))

claude = repo / "CLAUDE.md"
section = sub((T / "CLAUDE.memory-section.md").read_text())
prof_rules = [(PROFILES_DIR / l / f"rules.{lang}.md").read_text().strip() for l in layers if (PROFILES_DIR / l / f"rules.{lang}.md").exists() and l != "generic"]
if prof_rules:
    section = section.rstrip("\n") + ("\n\n### Perfil del proyecto\n\n" if lang == "es" else "\n\n### Project profile\n\n") + "\n\n".join(sub(r) for r in prof_rules) + "\n"
if claude.exists() and any(h in claude.read_text() for h in ("## Memoria del proyecto (Cognee)", "## Project memory (Cognee)")):
    print("  CLAUDE.md already has the memory section")
else:
    claude.write_text((claude.read_text() if claude.exists() else "# CLAUDE.md\n") + section, encoding="utf-8")
    print("  CLAUDE.md: memory section added")

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
print("  SessionStart/PreCompact/SessionEnd hooks in .claude/settings.local.json (local file, not versioned)")

subprocess.run([str(S / "install_skills.sh"), str(repo)], check=True)

# OpenSpec: part of the installation (drives the implementations; see the rule in CLAUDE.md)
import shutil
if a.openspec != "no":
    if (repo / "openspec").is_dir():
        print("  OpenSpec already initialized in the repo")
    elif shutil.which("openspec"):
        r = subprocess.run(["openspec", "init", "--tools", "claude", "--language", lang, "--no-animation", str(repo)], capture_output=True, text=True)
        print("  OpenSpec initialized (openspec/, skills and /opsx:* commands in .claude/)" if r.returncode == 0 else f"  OpenSpec init failed: {(r.stdout + r.stderr)[-200:]}")
    else:
        msg = "OPENSPEC_MISSING: install the CLI (see SEED.md, requirements) and run `openspec init --tools claude --language " + lang + "` in the repo."
        print("  " + msg, file=sys.stderr)
        if a.openspec == "yes":
            sys.exit(4)
ex = repo / ".git/info/exclude"
for line in ("docs/agent-memory/handoffs/_local/", ".agent-memory/local.yaml"):
    if line not in ex.read_text():
        ex.write_text(ex.read_text().rstrip("\n") + "\n" + line + "\n")
print(f"\nDone. Next: write docs/agent-memory/project.md and the first documents, then\n"
      f"  {S}/memctl.sh sync {repo} --apply\n  (stack up and plugin/MCP configured: see spec 21)")
