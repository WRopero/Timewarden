#!/usr/bin/env python3
"""Obsolescencia por Git, sin tokens: para cada doc, ¿cambiaron sus source_paths desde source_commit?

Uso: memory_stale.py <repo> [doc.md ...]     (sin docs = todos los de docs/agent-memory)
Salida por doc: FRESCO | OBSOLETO (archivos cambiados) | SIN-FUENTE. Exit 1 si hay obsoletos.
CLAUDE.md y AGENTS.md se ignoran como fuente (cambian a diario); ver stale_ignore en project.yaml.
"""
import re, subprocess, sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
docs = [Path(a) for a in sys.argv[2:]] or sorted((repo / "docs/agent-memory").rglob("*.md"))
stale = 0
# Fuentes "blandas": archivos que cambian a diario y que muchos documentos citan solo como contexto.
# No marcan obsolescencia por si solas. Se puede cambiar en .agent-memory/project.yaml -> stale_ignore: [a, b]
SOFT = ["CLAUDE.md", "AGENTS.md"]
cfgp = repo / ".agent-memory" / "project.yaml"
if cfgp.exists():
    m_ = re.search(r"^stale_ignore:\s*\[(.*?)\]", cfgp.read_text(encoding="utf-8"), re.M)
    if m_:
        SOFT = [x.strip().strip("'\"") for x in m_.group(1).split(",") if x.strip()]
for d in docs:
    d = d if d.is_absolute() else repo / d
    m = re.match(r"^---\n(.*?)\n---\n", d.read_text(encoding="utf-8"), re.S)
    meta = m.group(1) if m else ""
    commit = (re.search(r"^source_commit:\s*(\S+)", meta, re.M) or [None, ""])[1]
    block = re.search(r"^source_paths:\s*\n((?:\s+-\s+.*\n?)+)", meta + "\n", re.M)
    paths = [x.strip()[2:].strip() for x in block.group(1).splitlines()] if block else []
    rel = d.relative_to(repo).as_posix()
    if not commit or commit.startswith("<") or not paths:
        print(f"SIN-FUENTE  {rel}"); continue
    out = subprocess.run(["git", "-C", str(repo), "diff", "--name-only", f"{commit}..HEAD", "--", *paths],
                         capture_output=True, text=True)
    if out.returncode != 0:
        print(f"SIN-FUENTE  {rel} (commit {commit} no resuelve)"); continue
    changed = [c for c in out.stdout.split() if c not in SOFT]
    if changed:
        stale += 1; print(f"OBSOLETO    {rel}: {', '.join(changed)}")
    else:
        print(f"FRESCO      {rel}")
sys.exit(1 if stale else 0)
