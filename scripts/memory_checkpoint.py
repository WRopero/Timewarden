#!/usr/bin/env python3
"""Deterministic checkpoint at session end (SessionEnd/PreCompact hook). No LLM, 0 tokens.

Writes docs/agent-memory/handoffs/_local/auto-<branch>.md with: branch, HEAD, uncommitted changes,
latest commits, and the user's latest prompts (from the transcript). Reasoning and
decisions are saved by the project-memory-handoff skill; this only prevents losing the thread.
Input: hook JSON via stdin (transcript_path, cwd). Usage: memory_checkpoint.py [<repo>]
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
lines = [f"# Automatic checkpoint ({time.strftime('%Y-%m-%d %H:%M')})", "",
         f"- Branch: {branch} · HEAD: {git('rev-parse', '--short', 'HEAD')}",
         f"- Uncommitted changes: {len(status)}"]
lines += [f"  - {s}" for s in status[:15]] + (["  - …"] if len(status) > 15 else [])
lines += ["- Latest commits:"] + [f"  - {c}" for c in git("log", "--oneline", "-5").splitlines()]
if prompts:
    lines += ["- Latest user requests (to pick the thread back up):"] + [f"  - {p}" for p in prompts[-3:]]
lines += ["", "(Generated without an LLM. Decisions and the next step, if they matter, go in a real handoff.)"]
(dest / f"auto-{safe}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# Update the memory usage log for Management Memory (metadata only; never blocks shutdown)
try:
    subprocess.run([sys.executable, "-I", str(Path(__file__).parent / "usage_scan.py")], capture_output=True, timeout=15)
except Exception:
    pass
