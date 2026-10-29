#!/usr/bin/env python3
"""Memory consumption report (observer + captured sessions). No LLM.
Usage: weekly_report.py [--days 7] [--since YYYY-MM-DD]   (default: last 7 days)
Separating document ingestion (sync) from session closing (final improve) by time windows
is not possible; the observer total is reported per day, along with captured sessions per day.
"""
import argparse, collections, datetime as dt, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from cognee_adapter import Cognee

ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=7); ap.add_argument("--since")
a = ap.parse_args()
since = dt.datetime.fromisoformat(a.since) if a.since else dt.datetime.utcnow() - dt.timedelta(days=a.days)

per_day = collections.defaultdict(lambda: [0, 0])
for l in open(os.path.expanduser("~/.cognee-plugin/observer/observer-events.log")):
    try: e = json.loads(l)
    except json.JSONDecodeError: continue
    if e.get("event") != "completion": continue
    t = dt.datetime.fromisoformat(e["ts"].replace("+00:00", ""))
    if t >= since:
        d = per_day[t.strftime("%Y-%m-%d")]; d[0] += 1; d[1] += e["detail"].get("tokens") or 0
print(f"== Observer (Claude calls via subscription) since {since:%Y-%m-%d} UTC ==")
for day in sorted(per_day): print(f"  {day}: {per_day[day][0]:4d} calls  {per_day[day][1]:8d} tokens")
tot = [sum(v[i] for v in per_day.values()) for i in (0, 1)]
print(f"  TOTAL: {tot[0]} calls, {tot[1]} tokens")

try:
    c = Cognee(); ss = c._request("GET", "/api/v1/sessions")["sessions"]
    cl = [s for s in ss if s["session_id"].startswith("claude_")]
    by = collections.Counter(s["started_at"][:10] for s in cl if s["started_at"] >= since.isoformat())
    print(f"\n== Claude sessions captured on the server: {len(cl)} (since the date: {sum(by.values())}) ==")
    for d in sorted(by): print(f"  {d}: {by[d]}")
    if tot[0] and by: print(f"  calls per captured session (approx., includes syncs): {tot[0]/max(sum(by.values()),1):.1f}")
    print("\n== Datasets ==")
    for d in c.datasets():
        n = c._request("GET", f"/api/v1/datasets/{d['id']}/data/count")["count"]; print(f"  {d['name']}: {n} items")
except Exception as exc:
    print("\n(server unavailable:", str(exc)[:120], ")")
spool = list((Path.home() / ".cognee-plugin/claude-code/spool").glob("*.json"))
print(f"\nUnsent captures (spool): {len(spool)}" + ("  <- check worker (kill _cloud_worker.py)" if spool else ""))
cfg = (Path.home() / ".cognee/.env").read_text() if (Path.home() / ".cognee/.env").exists() else ""
cap = [l for l in cfg.splitlines() if l.startswith("COGNEE_CAPTURE=")]
print("Capture:", cap[-1] if cap else "(undefined)")
