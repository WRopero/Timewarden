#!/usr/bin/env python3
"""Extracts from Claude Code transcripts WHEN and HOW memory is used (metadata only, 0 tokens, no LLM).

Reads ~/.claude/projects/*/*.jsonl (read-only) and writes ~/.local/share/agents_memory_system/view/usage.jsonl,
which Management Memory shows in «Memory usage». One JSON line per event:
  briefing   SessionStart hook injected the briefing (chars)
  recall     memory query: via MCP (tool) or via the project-memory-recall skill (truncated query, dataset, ok/error, latency, chars)
  write      remember/handoff/document (memory was written or a write was requested)
  plugin     plugin summary when opening a session («recall hit rate x/y», saved entries)
Only the query truncated to 160 characters and the result size are stored, never the returned text.
Usage: usage_scan.py [--projects-dir DIR] [--out FILE]
"""
import argparse, json, re
from datetime import datetime
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--projects-dir", default=str(Path.home() / ".claude" / "projects"))
ap.add_argument("--out", default=str(Path.home() / ".local/share/agents_memory_system/view/usage.jsonl"))
a = ap.parse_args()

RECALL_TOOLS = ("mcp__agents_cognee__recall", "mcp__agents_cognee__search")
WRITE_TOOLS = ("mcp__agents_cognee__remember",)
SKILL_KIND = {"project-memory-recall": "recall", "project-memory-handoff": "write", "project-memory-document": "write"}


def ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def clip(s, n=160):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def result_info(block):
    c = block.get("content")
    txt = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else ""
    err = bool(re.search(r"\bError\b|Client error|404|500", txt[:300])) or block.get("is_error")
    return len(txt), bool(err)


events = []
for f in sorted(Path(a.projects_dir).glob("*/*.jsonl")):
    pending = {}
    for line in f.open(encoding="utf-8", errors="replace"):
        if not any(k in line for k in ("agents_cognee", "project-memory", "SessionStart", "recall hit rate", "hook_system_message")):
            if '"tool_result"' not in line:
                continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        t, sid, cwd = ts(o.get("timestamp", "")) if o.get("timestamp") else None, o.get("sessionId") or f.stem, o.get("cwd")
        project = Path(cwd).name if cwd else f.parent.name
        att = o.get("attachment") or {}
        if att.get("type") == "hook_success" and att.get("hookEvent") == "SessionStart":
            out = att.get("stdout", "")
            m = re.search(r"(Memoria del proyecto \(briefing|Project memory \(startup briefing)", out)
            if m:
                events.append(dict(ts=t, session=sid, project=project, kind="briefing", chars=len(out), source=att.get("hookName", "")))
        if att.get("type") == "hook_system_message" and "recall hit rate" in str(att.get("content", "")):
            c = str(att["content"])
            h = re.search(r"recall hit rate (\d+)/(\d+)", c); sv = re.search(r"saved (\d+) entries", c); im = re.search(r"(\d+) improves", c)
            events.append(dict(ts=t, session=sid, project=project, kind="plugin", hits=int(h.group(1)) if h else None, asked=int(h.group(2)) if h else None,
                               saved=int(sv.group(1)) if sv else None, improves=int(im.group(1)) if im else None))
        msg = o.get("message") or {}
        if not isinstance(msg.get("content"), list):
            continue
        for b in msg["content"]:
            if b.get("type") == "tool_use":
                name, inp = b.get("name", ""), b.get("input") or {}
                if name in RECALL_TOOLS or name in WRITE_TOOLS:
                    ds = str(inp.get("datasets", "")).strip("[]\"' ")
                    pending[b["id"]] = dict(ts=t, session=sid, project=project, kind="recall" if name in RECALL_TOOLS else "write", via="mcp",
                                            query=clip(inp.get("query") or inp.get("data") or inp.get("text") or ""), dataset=ds, mode=inp.get("search_type"), top_k=inp.get("top_k"))
                elif name == "Skill" and inp.get("skill") in SKILL_KIND:
                    events.append(dict(ts=t, session=sid, project=project, kind=SKILL_KIND[inp["skill"]], via="skill:" + inp["skill"], query=clip(inp.get("args", ""))))
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                ev = pending.pop(b["tool_use_id"])
                chars, err = result_info(b)
                ev.update(chars=chars, ok=not err, latency_s=round(t - ev["ts"], 2) if t and ev["ts"] else None)
                events.append(ev)
    events.extend(pending.values())  # uses with no visible result

events = [e for e in events if e.get("ts")]
events.sort(key=lambda e: e["ts"])
out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
tmp = out.with_suffix(".tmp")
tmp.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + ("\n" if events else ""), encoding="utf-8")
tmp.replace(out)
kinds = {}
for e in events:
    kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
print(f"{len(events)} events -> {out}  {kinds}")
