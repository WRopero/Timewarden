#!/usr/bin/env python3
"""Git-based staleness, no tokens: for each doc, did its source_paths change since source_commit?

Usage: memory_stale.py <repo> [doc.md ...]     (no docs = all of those in docs/agent-memory)
Output per doc: FRESH | STALE (changed files) | NO-SOURCE. Exit 1 if any are stale.
CLAUDE.md and AGENTS.md are ignored as sources (they change daily); see stale_ignore in project.yaml.
"""
import re, subprocess, sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
docs = [Path(a) for a in sys.argv[2:]] or sorted((repo / "docs/agent-memory").rglob("*.md"))
stale = 0
# "Soft" sources: files that change daily and that many documents cite only as context.
# They do not flag staleness on their own. Can be changed in .agent-memory/project.yaml -> stale_ignore: [a, b]
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
        print(f"NO-SOURCE  {rel}"); continue
    out = subprocess.run(["git", "-C", str(repo), "diff", "--name-only", f"{commit}..HEAD", "--", *paths],
                         capture_output=True, text=True)
    if out.returncode != 0:
        print(f"NO-SOURCE  {rel} (commit {commit} does not resolve)"); continue
    changed = [c for c in out.stdout.split() if c not in SOFT]
    if changed:
        stale += 1; print(f"STALE    {rel}: {', '.join(changed)}")
    else:
        print(f"FRESH      {rel}")
sys.exit(1 if stale else 0)
