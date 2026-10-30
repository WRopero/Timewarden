#!/usr/bin/env python3
"""Change-driven sync of the data project graph and connection catalog. Does nothing unless something changed.

Usage: data_sync.py [--repo DIR] <command>
  hook                      SessionStart entry: prints ONE briefing line and, if sources changed or a live check is due,
                            launches `run` detached (never blocks the session, never fails it)
  run [--force] [--live auto|off|force] [--index auto|off|now]
                            fingerprint -> (live signature) -> rebuild only if changed -> index only changed documents
  status                    last result, in one line

Fingerprints: tier A = content hash of the repo files that can change the graph; tier B (only environments with
`metadata_sync: true`, at most once per TTL) = a cheap metadata signature. Documents are written byte-stable, so the
memory sync (hash-based) re-indexes only documents whose content actually changed.
Config (.agent-memory/project.yaml, all optional):
  data_graph: {auto_sync: true, tool_exports: auto|off, live_ttl_hours: 6, max_auto_sync_docs: 20}
"""
from __future__ import annotations

import argparse
import fcntl
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import data_connect as dc  # noqa: E402
import data_graph as dg  # noqa: E402
import data_sources as ds  # noqa: E402
import miniyaml  # noqa: E402

STATE_REL = ".agent-memory/data-sync-state"
DATA_LAYERS = {"dbt", "dataform", "databricks"}


def paths(repo: Path):
    d = repo / STATE_REL
    return d, d / "state.json", d / "live.json", d / "sync.lock"


def config(repo: Path) -> dict:
    y = {}
    p = repo / ".agent-memory" / "project.yaml"
    if p.exists():
        y = miniyaml.load(p.read_text(encoding="utf-8")) or {}
    c = y.get("data_graph") if isinstance(y.get("data_graph"), dict) else {}
    return {"auto_sync": c.get("auto_sync", True) is not False, "auto_baseline": c.get("auto_baseline", True) is not False,
            "auto_enable_live": c.get("auto_enable_live", True) is not False, "tool_exports": str(c.get("tool_exports", "auto")),
            "live_ttl_hours": float(c.get("live_ttl_hours", 6)), "max_auto_sync_docs": int(c.get("max_auto_sync_docs", 20)),
            "max_baseline_docs": int(c.get("max_baseline_docs", 60)), "profile": str(y.get("profile", ""))}


def is_data_project(repo: Path, cfg: dict) -> bool:
    return bool(DATA_LAYERS & set(cfg["profile"].split(","))) or (repo / dg.OUT_REL / "graph.json").exists()


def load_state(sp: Path) -> dict:
    try:
        return json.loads(sp.read_text())
    except (OSError, ValueError):
        return {}


def save_state(sp: Path, st: dict):
    sp.parent.mkdir(parents=True, exist_ok=True)
    tmp = sp.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1, sort_keys=True))
    tmp.replace(sp)


def live_envs(repo: Path) -> dict:
    return {n: e for n, e in (dc.load(repo).get("environments") or {}).items() if isinstance(e, dict) and e.get("metadata_sync") is True}


def live_due(st: dict, name: str, ttl_h: float) -> bool:
    return time.time() - st.get("live", {}).get(name, {}).get("checked_at", 0) >= ttl_h * 3600


def stack_up() -> bool:
    try:
        sys.path.insert(0, str(HERE))
        from cognee_adapter import BASE_URL
        urllib.request.urlopen(BASE_URL.rstrip("/") + "/health", timeout=2).read()
        return True
    except Exception:
        return False


def index_plan(repo: Path) -> dict[str, int]:
    r = subprocess.run([sys.executable, "-I", str(HERE / "sync_markdown.py"), str(repo), "--only", dg.OUT_REL, "--only", dc.DOC],
                       capture_output=True, text=True, timeout=60)
    m = re.search(r"project=\S+: (.*)", r.stdout)
    return {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", m.group(1))} if m else {}


def run(repo: Path, force=False, live="auto", index="auto") -> dict:
    cfg = config(repo)
    sd, sp, lp, lock = paths(repo)
    sd.mkdir(parents=True, exist_ok=True)
    res = {"changed": False, "live": {}, "errors": [], "indexed": "none"}
    with lock.open("w") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {**res, "errors": ["another sync is running"]}
        st = load_state(sp)
        fp = dg.fingerprint(repo)
        changed = force or fp != st.get("fingerprint") or not (repo / dg.OUT_REL / "graph.json").exists()
        # zero-touch: fill identifiers from the user's authenticated CLIs and enable live metadata where a read-only probe works
        if live != "off" and cfg["auto_enable_live"] and (repo / dc.CATALOG).exists():
            def probe(env):
                ad = ds.adapter_for(env)
                if not ad:
                    return False, f"no live adapter for {env.get('warehouse')}"
                miss = ds.required_ids(env)
                if miss:
                    return False, "identifiers missing: " + ", ".join(miss)
                try:
                    return True, "signature " + ad[0](env)[:60]
                except ds.LiveError as exc:
                    return False, str(exc)
            try:
                res["discovery"] = dc.discover(repo, ds.RUN) + dc.enable_live(repo, probe)
            except Exception as exc:
                res["errors"].append(f"discovery: {str(exc)[:120]}")
        # tier B: live metadata, rate-limited by TTL, and only fully fetched when its signature moved
        envs = live_envs(repo) if live != "off" else {}
        for name, e in envs.items():
            lst = st.setdefault("live", {}).setdefault(name, {})
            if live != "force" and not live_due(st, name, cfg["live_ttl_hours"]) and (sd / f"live-{name}.json").exists():
                continue
            ad = ds.adapter_for(e)
            if not ad:
                res["errors"].append(f"{name}: no live adapter for {e.get('warehouse')}")
                continue
            try:
                sig = ad[0](e)
                lst["checked_at"] = time.time()
                if live == "force" or sig != lst.get("signature") or not (sd / f"live-{name}.json").exists():
                    data = ad[1](e)
                    (sd / f"live-{name}.json").write_text(json.dumps(data, sort_keys=True))
                    lst.update(signature=sig, fetched_at=time.time(), tables=len(data["tables"]))
                    res["live"][name] = f"fetched {len(data['tables'])} tables"
                    changed = True
                else:
                    res["live"][name] = "unchanged"
            except ds.LiveError as exc:
                res["errors"].append(f"{name}: {exc}")
        merged = {"scanned": [], "tables": []}
        for name in envs:
            f = sd / f"live-{name}.json"
            if f.exists():
                d = json.loads(f.read_text())
                merged["scanned"] += d["scanned"]; merged["tables"] += d["tables"]
        if merged["tables"] and (not lp.exists() or json.loads(lp.read_text()) != merged):
            lp.write_text(json.dumps(merged, sort_keys=True)); changed = True
        elif not merged["tables"] and lp.exists():
            lp.unlink(); changed = True
        if changed:
            d = dg.build(repo, cfg["tool_exports"] if cfg["tool_exports"] in ("auto", "off", "run") else "auto")
            res.update(changed=True, nodes=len(d["nodes"]), edges=len(d["edges"]),
                       tier=",".join(f"{k}:{v.get('tier')}" for k, v in d["sources"].items() if isinstance(v, dict) and v.get("tier")))
            st["fingerprint"] = fp
            st["graph"] = {"nodes": len(d["nodes"]), "edges": len(d["edges"]), "tier": res["tier"], "built_at": time.time()}
        if (repo / dc.CATALOG).exists():
            txt = dc.render(repo)
            out = repo / dc.DOC
            out.parent.mkdir(parents=True, exist_ok=True)
            if not out.exists() or out.read_text() != txt:
                out.write_text(txt, encoding="utf-8")
        # indexing: only documents whose hash changed (the sync registry decides); bounded; deferred if the stack is down
        if index != "off" and (cfg["auto_sync"] or index == "now"):
            plan = index_plan(repo)
            n = sum(plan.get(k, 0) for k in ("new", "changed", "retry", "deleted"))
            baseline = plan.get("unchanged", 0) + plan.get("changed", 0) + plan.get("retry", 0) > 0
            cap = 0 if index == "now" else (cfg["max_auto_sync_docs"] if baseline else cfg["max_baseline_docs"])
            if n == 0:
                res["indexed"] = "current"
            elif not baseline and not cfg["auto_baseline"] and index != "now":
                res["indexed"] = f"baseline pending ({plan.get('new', 0)} documents never indexed; auto_baseline is off): run `memctl.sh sync <repo> --apply`"
            elif not stack_up():
                res["indexed"] = f"pending {n} (memory stack is down)"
            else:
                cmd = [sys.executable, "-I", str(HERE / "sync_markdown.py"), str(repo), "--apply", "--only", dg.OUT_REL, "--only", dc.DOC]
                if cap:
                    cmd += ["--max-docs", str(cap)]
                if index == "now":
                    subprocess.run(cmd, timeout=3600)
                else:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
                shown = n if not cap else min(n, cap)
                res["indexed"] = f"{n} synced" if index == "now" else f"{shown} of {n} queued" + ("" if baseline else " (first indexing, runs in the background)")
        st["last"] = {"at": time.time(), "result": res}
        save_state(sp, st)
    return res


def line(repo: Path) -> tuple[str, bool]:
    """One briefing line, and whether a background run is needed."""
    cfg = config(repo)
    if not is_data_project(repo, cfg):
        return "", False
    sd, sp, lp, _ = paths(repo)
    st = load_state(sp)
    g = st.get("graph")
    fp = dg.fingerprint(repo)
    stale = fp != st.get("fingerprint")
    due = [n for n in live_envs(repo) if live_due(st, n, cfg["live_ttl_hours"])]
    parts = []
    if not g:
        parts.append("Data graph: not built yet, building in the background")
    else:
        parts.append(f"Data graph: {g['nodes']} nodes / {g['edges']} relations ({g['tier'] or 'n/a'})" + (", sources changed, refreshing in the background" if stale else ", current"))
        parts.append("query it before asking or reading files: `python3 -I <MS>/scripts/data_graph.py impact|upstream|downstream|show <node>`")
    last = st.get("last", {}).get("result", {})
    if live_envs(repo):
        ages = [f"{n} {int((time.time() - v.get('fetched_at', 0)) / 3600)}h" for n, v in st.get("live", {}).items() if v.get("fetched_at")]
        parts.append("live metadata: " + (", ".join(ages) if ages else "not fetched yet") + (" (refresh due)" if due else ""))
    if last.get("errors"):
        parts.append("last sync issues: " + "; ".join(last["errors"])[:160])
    for note in last.get("discovery", [])[:3]:
        parts.append(note)
    if last.get("indexed", "").startswith(("pending", "baseline")):
        parts.append(last["indexed"])
    return ". ".join(parts) + ".", (stale or not g or bool(due))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--force", action="store_true"); r.add_argument("--live", choices=("auto", "off", "force"), default="auto")
    r.add_argument("--index", choices=("auto", "off", "now"), default="auto")
    sub.add_parser("hook"); sub.add_parser("status")
    a = ap.parse_args()
    repo = a.repo.resolve()
    if a.cmd == "run":
        res = run(repo, a.force, a.live, a.index)
        print(("rebuilt: " + f"{res.get('nodes')} nodes, {res.get('edges')} edges ({res.get('tier')})") if res["changed"] else "nothing changed: no rebuild, no indexing needed",
              f"| live: {res['live'] or 'off'} | index: {res['indexed']}" + (f" | issues: {res['errors']}" if res["errors"] else ""))
        return 0
    text, need = line(repo)
    if a.cmd == "status":
        print(text or "not a data project"); return 0
    if text:
        print(text)
    if need:
        try:
            subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve()), "--repo", str(repo), "run"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
