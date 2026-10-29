#!/usr/bin/env python3
"""Normalizes OTLP telemetry (Claude Code) + observer events into DuckDB and reports on them.

Sources (one authoritative per call, no summing of duplicates):
  - Claude Code: `claude_code.api_request` logs (one record per call, with categories).
  - Observer:    observer-events.log (total tokens; unknown categories = NULL, not 0).
The `claude_code.token.usage` metrics (delta) are only used to reconcile totals.
Idempotent: the primary key is the event hash.

Usage: normalize_usage.py [--telemetry DIR] [--observer FILE] [--db FILE] report [--project ID]
"""
import argparse, glob, hashlib, json, os, sys
import duckdb

DDL = """
CREATE TABLE IF NOT EXISTS calls (
  event_id VARCHAR PRIMARY KEY, ts TIMESTAMP, source VARCHAR, project_id VARCHAR, run_id VARCHAR,
  variant VARCHAR, actor VARCHAR, phase VARCHAR, session_id VARCHAR, prompt_id VARCHAR, model VARCHAR,
  input_tokens BIGINT, output_tokens BIGINT, cache_read_tokens BIGINT, cache_creation_tokens BIGINT,
  total_tokens BIGINT, cost_usd DOUBLE, duration_ms BIGINT);
CREATE TABLE IF NOT EXISTS metric_totals (
  file_hash VARCHAR, project_id VARCHAR, run_id VARCHAR, variant VARCHAR, model VARCHAR, kind VARCHAR, value DOUBLE,
  PRIMARY KEY (file_hash, project_id, run_id, model, kind));
"""


def attrs(items):
    out = {}
    for x in items or []:
        v = x["value"]
        out[x["key"]] = next(iter(v.values())) if v else None
    return out


def num(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def load_otlp(con, files):
    n_calls = n_metrics = 0
    for f in files:
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            doc = json.loads(line)
            for rl in doc.get("resourceLogs", []):
                res = attrs(rl["resource"]["attributes"])
                for sl in rl["scopeLogs"]:
                    for lr in sl["logRecords"]:
                        a = attrs(lr.get("attributes"))
                        if a.get("event.name") != "api_request":
                            continue
                        key = json.dumps([lr.get("timeUnixNano"), a.get("session.id"), a.get("prompt.id"),
                                          a.get("input_tokens"), a.get("output_tokens")], sort_keys=True)
                        eid = "otel:" + hashlib.sha256(key.encode()).hexdigest()[:24]
                        i, o = num(a.get("input_tokens")), num(a.get("output_tokens"))
                        cr, cc = num(a.get("cache_read_tokens")), num(a.get("cache_creation_tokens"))
                        total = sum(v for v in (i, o, cr, cc) if v is not None) if any(v is not None for v in (i, o, cr, cc)) else None
                        con.execute("INSERT OR IGNORE INTO calls VALUES (?,to_timestamp(?/1e9),?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                            eid, int(lr.get("timeUnixNano", 0)), "otel_log", res.get("project_id"), res.get("run_id"),
                            res.get("variant"), res.get("actor", "main_agent"), a.get("phase", "task"),
                            a.get("session.id"), a.get("prompt.id"), a.get("model"), i, o, cr, cc, total,
                            float(a["cost_usd"]) if a.get("cost_usd") is not None else None, num(a.get("duration_ms"))])
                        n_calls += 1
            fh = hashlib.sha256(os.path.basename(f).encode()).hexdigest()[:12]
            for rm in doc.get("resourceMetrics", []):
                res = attrs(rm["resource"]["attributes"])
                for sm in rm["scopeMetrics"]:
                    for m in sm["metrics"]:
                        if m["name"] != "claude_code.token.usage":
                            continue
                        for p in (m.get("sum") or {}).get("dataPoints", []):
                            a = attrs(p.get("attributes"))
                            con.execute("INSERT OR IGNORE INTO metric_totals VALUES (?,?,?,?,?,?,?)", [
                                fh + hashlib.sha256(line.encode()).hexdigest()[:8], res.get("project_id"), res.get("run_id"),
                                res.get("variant"), a.get("model"), a.get("type"),
                                float(p.get("asInt") or p.get("asDouble") or 0)])
                            n_metrics += 1
    return n_calls, n_metrics


def load_observer(con, path, project_id):
    n = 0
    if not os.path.exists(path):
        return 0
    for line in open(path, encoding="utf-8"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("event") != "completion":
            continue
        d = e.get("detail", {})
        eid = "obs:" + hashlib.sha256(line.encode()).hexdigest()[:24]
        con.execute("INSERT OR IGNORE INTO calls VALUES (?,?::TIMESTAMP,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            eid, e["ts"].replace("+00:00", ""), "observer_log", project_id, None, None, "observer", "ingestion",
            None, None, d.get("model"), None, None, None, None, d.get("tokens"), None, d.get("duration_ms")])
        n += 1
    return n


def report(con, project):
    w = "WHERE project_id = ?" if project else ""
    p = [project] if project else []
    print("\n== Usage by project / run / variant / actor ==")
    q = f"""SELECT coalesce(project_id,'(no project)') project, coalesce(run_id,'-') run, coalesce(variant,'-') var, actor,
        count(*) calls, sum(input_tokens) in_tok, sum(output_tokens) out_tok, sum(cache_read_tokens) cache_r,
        sum(cache_creation_tokens) cache_w, sum(total_tokens) total, round(sum(cost_usd),5) cost_usd,
        round(quantile_cont(duration_ms,0.5)) p50_ms
        FROM calls {w} GROUP BY ALL ORDER BY 1,2,4"""
    print(con.execute(q, p).fetch_df().to_string(index=False) if con.execute(f"SELECT count(*) FROM calls {w}", p).fetchone()[0] else "(no data)")
    print("\n== Coverage ==")
    print(con.execute(f"""SELECT count(*) calls,
        count(*) FILTER (WHERE total_tokens IS NULL) no_count,
        count(*) FILTER (WHERE project_id IS NULL) no_project,
        count(*) FILTER (WHERE input_tokens IS NULL AND total_tokens IS NOT NULL) unknown_categories
        FROM calls {w}""", p).fetch_df().to_string(index=False))
    print("\n== Reconciliation: logs (authoritative) vs delta metrics ==")
    q = f"""WITH l AS (
          SELECT run_id, 'input' kind, sum(input_tokens) v FROM calls {w + (' AND ' if w else 'WHERE ')}source='otel_log' GROUP BY 1
          UNION ALL SELECT run_id,'output',sum(output_tokens) FROM calls {w + (' AND ' if w else 'WHERE ')}source='otel_log' GROUP BY 1
          UNION ALL SELECT run_id,'cacheRead',sum(cache_read_tokens) FROM calls {w + (' AND ' if w else 'WHERE ')}source='otel_log' GROUP BY 1
          UNION ALL SELECT run_id,'cacheCreation',sum(cache_creation_tokens) FROM calls {w + (' AND ' if w else 'WHERE ')}source='otel_log' GROUP BY 1),
        m AS (SELECT run_id, kind, sum(value) v FROM metric_totals {w} GROUP BY 1,2)
        SELECT l.run_id, l.kind, l.v logs, m.v metrics,
               round(100.0*(coalesce(m.v,0)-l.v)/nullif(l.v,0),1) diff_pct
        FROM l LEFT JOIN m USING (run_id, kind) ORDER BY 1,2"""
    print(con.execute(q, p * 4 + p).fetch_df().to_string(index=False))
    print("(negative diff_pct = the metrics undercount: the last export window is not flushed when the session closes)")


def compare(con, project):
    """Average PER RUN (A and B may have a different number of runs).
    Relative savings = 1 - B/A, only if both variants have runs."""
    rows = con.execute("""SELECT variant, count(*) runs, avg(tok) tok, avg(costo) costo FROM (
        SELECT variant, run_id, sum(total_tokens) tok, sum(cost_usd) costo FROM calls
        WHERE project_id=? AND variant IN ('A','B') AND source='otel_log' GROUP BY 1,2) GROUP BY 1""", [project]).fetchall()
    d = {r[0]: r for r in rows}
    if "A" not in d or "B" not in d:
        print("\n== A/B: missing variants (needs A and B) =="); return
    a, b = d["A"], d["B"]
    print(f"\n== A/B project {project} (average per run, main agent only) ==")
    print(f"A: runs={a[1]} tokens={a[2]:.0f} cost=${a[3]:.4f}   B: runs={b[1]} tokens={b[2]:.0f} cost=${b[3]:.4f}")
    print(f"Cost B/A = {b[3]/a[3]:.1f}x   Relative savings (tokens) = {1 - b[2]/a[2]:.1%}")
    print("PRELIMINARY: minimal sample. Ingestion (observer) still needs to be amortized and quality/success measured; a negative savings is a valid result.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--telemetry", default="/telemetry")
    ap.add_argument("--observer", default="/observer/observer-events.log")
    ap.add_argument("--db", default="/data/usage.duckdb")
    ap.add_argument("--observer-project", default="")
    ap.add_argument("cmd", nargs="?", default="report", choices=["report"])
    ap.add_argument("--project")
    a = ap.parse_args()
    con = duckdb.connect(a.db)
    for stmt in DDL.strip().split(";"):
        if stmt.strip():
            con.execute(stmt)
    files = sorted(glob.glob(os.path.join(a.telemetry, "otlp*.json")))
    nc, nm = load_otlp(con, files)
    no = load_observer(con, a.observer, a.observer_project)
    print(f"read: {len(files)} OTLP files -> {nc} api_request calls, {nm} metric points; observer: {no} completions")
    report(con, a.project)
    if a.project:
        compare(con, a.project)


if __name__ == "__main__":
    sys.exit(main())
