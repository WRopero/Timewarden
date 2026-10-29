#!/usr/bin/env python3
"""Checkpoint determinista al terminar la sesion (hook SessionEnd/PreCompact). Sin LLM, 0 tokens.

Escribe docs/agent-memory/handoffs/_local/auto-<rama>.md con: rama, HEAD, cambios sin commit,
ultimos commits y los ultimos prompts del usuario (del transcript). El razonamiento y las
decisiones los guarda la skill project-memory-handoff; esto solo evita perder el hilo.
Entrada: JSON del hook por stdin (transcript_path, cwd). Uso: memory_checkpoint.py [<repo>]
"""
import json, re, subprocess, sys, time
from pathlib import Path

try:
    hook = json.load(sys.stdin) if not sys.stdin.isatty() else {}
except Exception:
    hook = {}
repo = Path(sys.argv[1] if len(sys.argv) > 1 else hook.get("cwd", ".")).resolve()
if not (repo / ".agent-memory" / "project.yaml").exists():
    sys.exit(0)


def git(*a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()


branch = git("branch", "--show-current") or "detached"
prompts = []
tp = hook.get("transcript_path")
if tp and Path(tp).exists():
    for line in Path(tp).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = e.get("message", {})
        if e.get("type") == "user" and msg.get("role") == "user" and isinstance(msg.get("content"), str):
            t = " ".join(msg["content"].split())
            if t and not t.startswith("<"):
                prompts.append(t[:220])
status = git("status", "--short").splitlines()
safe = re.sub(r"[^A-Za-z0-9._-]", "_", branch)
dest = repo / "docs" / "agent-memory" / "handoffs" / "_local"
dest.mkdir(parents=True, exist_ok=True)
lines = [f"# Checkpoint automatico ({time.strftime('%Y-%m-%d %H:%M')})", "",
         f"- Rama: {branch} · HEAD: {git('rev-parse', '--short', 'HEAD')}",
         f"- Cambios sin commit: {len(status)}"]
lines += [f"  - {s}" for s in status[:15]] + (["  - …"] if len(status) > 15 else [])
lines += ["- Ultimos commits:"] + [f"  - {c}" for c in git("log", "--oneline", "-5").splitlines()]
if prompts:
    lines += ["- Ultimos pedidos del usuario (para retomar el hilo):"] + [f"  - {p}" for p in prompts[-3:]]
lines += ["", "(Generado sin LLM. Las decisiones y el siguiente paso, si importan, van en un handoff real.)"]
(dest / f"auto-{safe}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# Actualiza el registro de uso de la memoria para Management Memory (solo metadatos; nunca bloquea el cierre)
try:
    subprocess.run([sys.executable, "-I", str(Path(__file__).parent / "usage_scan.py")], capture_output=True, timeout=15)
except Exception:
    pass
