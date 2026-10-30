"""Tier B: read-only METADATA from the live data system (BigQuery, Snowflake, Databricks).

Opt-in per environment (`metadata_sync: true` in .agent-memory/connections.yaml). Uses the user's own CLI and existing
authentication; never reads table data, never writes, never runs jobs. Each adapter has a cheap `signature()` (one
small metadata query) so the sync only does the full `fetch()` when something changed.
Output shape consumed by data_graph.merge_live():
  {"scanned": ["db.schema", ...], "tables": [{"db","schema","name","type","rows","columns":[{"name","type","partition","cluster"}]}]}
"""
from __future__ import annotations

import json
import re
import subprocess

READONLY = re.compile(r"^\s*(select|with|show|describe)\b", re.I)
FORBIDDEN = re.compile(r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|call|copy|put|remove)\b", re.I)


class LiveError(RuntimeError):
    pass


def RUN(cmd: list[str], timeout: int = 120) -> str:   # replaced by tests
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise LiveError(f"{cmd[0]} is not installed")
    except subprocess.TimeoutExpired:
        raise LiveError(f"{cmd[0]} timed out")
    if r.returncode != 0:
        raise LiveError(f"{cmd[0]} failed: {(r.stderr or r.stdout).strip()[:200]}")
    return r.stdout


def _sql_guard(sql: str) -> str:
    if not READONLY.match(sql) or FORBIDDEN.search(re.sub(r"'[^']*'", "''", sql)):
        raise LiveError("refusing to run a non read-only statement")
    return sql


def _json(out: str):
    try:
        return json.loads(out)
    except ValueError:
        raise LiveError("unexpected non-JSON output from the CLI")


def _ids(env: dict, key: str) -> list[str]:
    v = (env.get("identifiers") or {}).get(key)
    return [str(x) for x in v] if isinstance(v, list) else ([str(v)] if v else [])


# ------------------------------------------------------------------ BigQuery
def _bq(project: str, sql: str, location: str = "") -> list[dict]:
    cmd = ["bq", "query", "--nouse_legacy_sql", "--format=json", "--max_rows=200000", f"--project_id={project}"]
    if location:
        cmd.append(f"--location={location}")
    return _json(RUN(cmd + [_sql_guard(sql)])) or []


def bigquery_signature(env: dict) -> str:
    ids = env.get("identifiers") or {}
    project, loc = str(ids.get("project", "")), str(ids.get("location", ""))
    parts = []
    for ds in _ids(env, "datasets") or _ids(env, "dataset"):
        row = (_bq(project, f"SELECT COUNT(*) c, MAX(last_modified_time) m FROM `{project}.{ds}.__TABLES__`", loc) or [{}])[0]
        parts.append(f"{ds}:{row.get('c')}:{row.get('m')}")
    return "|".join(parts)


def bigquery_fetch(env: dict) -> dict:
    ids = env.get("identifiers") or {}
    project, loc = str(ids.get("project", "")), str(ids.get("location", ""))
    tables, scanned = [], []
    for ds in _ids(env, "datasets") or _ids(env, "dataset"):
        scanned.append(f"{project}.{ds}")
        meta = {r["table_id"]: r for r in _bq(project, f"SELECT table_id, type, row_count FROM `{project}.{ds}.__TABLES__`", loc)}
        cols: dict[str, list] = {}
        for r in _bq(project, f"SELECT table_name, column_name, data_type, is_partitioning_column, clustering_ordinal_position "
                              f"FROM `{project}.{ds}.INFORMATION_SCHEMA.COLUMNS` ORDER BY table_name, ordinal_position", loc):
            cols.setdefault(r["table_name"], []).append({"name": r["column_name"], "type": r["data_type"], "partition": r.get("is_partitioning_column") == "YES",
                                                         "cluster": int(r["clustering_ordinal_position"]) if r.get("clustering_ordinal_position") not in (None, "") else 0})
        for name, m in sorted(meta.items()):
            tables.append({"db": project, "schema": ds, "name": name, "type": {"1": "table", "2": "view"}.get(str(m.get("type")), "table"),
                           "rows": int(m["row_count"]) if m.get("row_count") not in (None, "") else None, "columns": cols.get(name, [])})
    return {"scanned": scanned, "tables": tables}


# ------------------------------------------------------------------ Snowflake
def _sf(env: dict, sql: str) -> list[dict]:
    ids = env.get("identifiers") or {}
    cmd = ["snow", "sql", "--format", "json", "-q", _sql_guard(sql)]
    if ids.get("connection"):
        cmd += ["-c", str(ids["connection"])]
    return _json(RUN(cmd)) or []


def snowflake_signature(env: dict) -> str:
    db = str((env.get("identifiers") or {}).get("database", ""))
    row = (_sf(env, f"SELECT COUNT(*) AS C, MAX(LAST_ALTERED) AS M FROM {db}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA <> 'INFORMATION_SCHEMA'") or [{}])[0]
    return f"{row.get('C')}:{row.get('M')}"


def snowflake_fetch(env: dict) -> dict:
    ids = env.get("identifiers") or {}
    db = str(ids.get("database", ""))
    schemas = _ids(env, "schemas")
    flt = ("AND TABLE_SCHEMA IN (" + ",".join(f"'{s.upper()}'" for s in schemas) + ")") if schemas else ""
    meta = _sf(env, f"SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, ROW_COUNT FROM {db}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA <> 'INFORMATION_SCHEMA' {flt}")
    cols: dict[tuple, list] = {}
    for r in _sf(env, f"SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM {db}.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA <> 'INFORMATION_SCHEMA' {flt} ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"):
        cols.setdefault((r["TABLE_SCHEMA"], r["TABLE_NAME"]), []).append({"name": r["COLUMN_NAME"], "type": r["DATA_TYPE"], "partition": False, "cluster": 0})
    tables = [{"db": db, "schema": m["TABLE_SCHEMA"], "name": m["TABLE_NAME"], "type": "view" if "VIEW" in str(m.get("TABLE_TYPE", "")).upper() else "table",
               "rows": int(m["ROW_COUNT"]) if m.get("ROW_COUNT") not in (None, "") else None, "columns": cols.get((m["TABLE_SCHEMA"], m["TABLE_NAME"]), [])} for m in meta]
    tables.sort(key=lambda t: (t["schema"], t["name"]))
    return {"scanned": sorted({f"{db}.{t['schema']}" for t in tables}), "tables": tables}


# ------------------------------------------------------------------ Databricks
def _dbx_tables(env: dict) -> list[tuple[str, str, dict]]:
    ids = env.get("identifiers") or {}
    cat = str(ids.get("catalog", ""))
    out = []
    for sch in _ids(env, "schemas") or _ids(env, "schema"):
        cmd = ["databricks", "tables", "list", cat, sch, "--output", "json"]
        if ids.get("profile"):
            cmd += ["--profile", str(ids["profile"])]
        for t in _json(RUN(cmd)) or []:
            out.append((cat, sch, t))
    return out


def databricks_signature(env: dict) -> str:
    ts = _dbx_tables(env)
    return f"{len(ts)}:{max((int(t.get('updated_at') or 0) for _, _, t in ts), default=0)}"


def databricks_fetch(env: dict) -> dict:
    tables, scanned = [], set()
    for cat, sch, t in _dbx_tables(env):
        scanned.add(f"{cat}.{sch}")
        cols = [{"name": c["name"], "type": c.get("type_text", ""), "partition": c.get("partition_index") is not None, "cluster": 0} for c in sorted(t.get("columns") or [], key=lambda c: c.get("position", 0))]
        tables.append({"db": cat, "schema": sch, "name": t["name"], "type": "view" if "VIEW" in str(t.get("table_type", "")).upper() else "table", "rows": None, "columns": cols})
    tables.sort(key=lambda t: (t["schema"], t["name"]))
    return {"scanned": sorted(scanned), "tables": tables}


ADAPTERS = {"bigquery": (bigquery_signature, bigquery_fetch), "snowflake": (snowflake_signature, snowflake_fetch), "databricks": (databricks_signature, databricks_fetch)}


def adapter_for(env: dict):
    w = str(env.get("warehouse") or env.get("system") or "").lower()
    for k, v in ADAPTERS.items():
        if k in w:
            return v
    return None
