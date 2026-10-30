#!/usr/bin/env python3
"""Detects the project type (layered profiles) from evidence in the repository. No network, no LLM.

Usage: detect_project_type.py <repo>
Output (one line, parseable): PROFILES=<a,b> CONFIDENCE=<0-1> EVIDENCE=<x;y> [ASK=<reason>] [OPTIONS=<a,b|c|...>]
Exit code: 0 = confident, 2 = ambiguous: the agent MUST ask the user and reinstall with --profile.
Layers: dbt, dataform, snowflake, bigquery, databricks, webapp, python-lib, generic. A project = 1 or 2 layers
(e.g. dbt+snowflake, dbt+bigquery, dbt+databricks, dataform+bigquery).
"""
import json, re, sys
from pathlib import Path

SKIP = {"node_modules", ".git", ".venv", "venv", "__pycache__", "target", "dbt_packages", ".terraform", "dist", "build"}
repo = Path(sys.argv[1]).resolve()


def files(pattern, limit=400):
    out = []
    for p in repo.rglob(pattern):
        if len(out) >= limit: break
        if p.is_file() and not any(x in SKIP for x in p.relative_to(repo).parts):
            out.append(p)
    return out


def text(p, n=60000):
    try: return p.read_text(encoding="utf-8", errors="ignore")[:n]
    except OSError: return ""


ev, score = [], {"dbt": 0, "dataform": 0, "snowflake": 0, "bigquery": 0, "databricks": 0, "webapp": 0, "python-lib": 0}


def add(layer, pts, why):
    score[layer] += pts; ev.append(f"{layer}:{why}")


# --- dbt
dbt_files = files("dbt_project.yml")
if dbt_files:
    add("dbt", 6, "dbt_project.yml")
    if files("packages.yml"): add("dbt", 1, "packages.yml")
    if files("*.sql") and any("models" in p.parts for p in files("*.sql")): add("dbt", 1, "models/*.sql")
# adapter: requirements/pyproject/profiles.yml/ packages
blob = " ".join(text(p) for pat in ("requirements*.txt", "pyproject.toml", "profiles.yml", "Pipfile", "poetry.lock") for p in files(pat, 20))
adapter_sf = bool(re.search(r"dbt[-_]snowflake|type:\s*snowflake", blob, re.I))
adapter_bq = bool(re.search(r"dbt[-_]bigquery|type:\s*bigquery", blob, re.I))
adapter_dbx = bool(re.search(r"dbt[-_]databricks|type:\s*databricks", blob, re.I))
if adapter_sf: add("snowflake", 4, "snowflake adapter/profile")
if adapter_bq: add("bigquery", 4, "bigquery adapter/profile")
if adapter_dbx: add("databricks", 4, "databricks adapter/profile")
# --- databricks (asset bundles, Delta Live Tables)
if files("databricks.yml", 10) or files("databricks.yaml", 10): add("databricks", 6, "databricks.yml bundle")
if any(re.search(r"^\s*(import dlt|from dlt)\b", text(p, 6000), re.M) for p in files("*.py", 80)): add("databricks", 3, "Delta Live Tables (dlt)")
# --- dataform
if files("workflow_settings.yaml") or files("dataform.json"): add("dataform", 6, "workflow_settings.yaml|dataform.json")
sqlx = [p for p in files("*.sqlx", 50)]
if sqlx: add("dataform", 3, f"{len(sqlx)}+ .sqlx files")
if any("@dataform/core" in text(p, 5000) for p in files("package.json", 10)): add("dataform", 2, "@dataform/core")
if score["dataform"]: add("bigquery", 4, "Dataform runs on BigQuery")
# --- standalone bigquery (SQL / Terraform / Python)
tf_bq = [p for p in files("*.tf", 60) if re.search(r"google_bigquery_", text(p, 20000))]
if tf_bq: add("bigquery", 4, "Terraform google_bigquery_*")
if any(re.search(r"google[-.]cloud[-.]bigquery|bigquery\.Client", text(p, 8000)) for p in files("*.py", 80)) or "google-cloud-bigquery" in blob:
    add("bigquery", 3, "google-cloud-bigquery client")
bq_sql = [p for p in files("*.sql", 80) if re.search(r"`[\w-]+\.[\w-]+\.[\w-]+`", text(p, 6000))]
if bq_sql and not dbt_files: add("bigquery", 2, f"{len(bq_sql)} .sql files with `project.dataset.table`")
if any(re.search(r"snowflake[-.]connector|snowflake\.snowpark|snowflake-sdk", text(p, 4000)) for p in files("requirements*.txt", 10) + files("pyproject.toml", 10) + files("package.json", 10)):
    add("snowflake", 3, "Snowflake connector")
# --- web application / library
web = False
for p in files("package.json", 10):
    if re.search(r'"(next|react|vue|svelte|express|nestjs|@nestjs/core|fastify)"', text(p, 8000)): web = True; add("webapp", 3, f"{p.relative_to(repo)} (web framework)"); break
if files("manage.py") or re.search(r"\b(django|fastapi|flask)\b", blob, re.I): web = True; add("webapp", 3, "Python web framework")
if not (dbt_files or score["dataform"]) and files("pyproject.toml", 5) and not web:
    add("python-lib", 2, "pyproject.toml without web framework")

layers = [k for k, v in score.items() if v >= 3]
conf, ask, opts = 0.0, None, []
data_core = [k for k in layers if k in ("dbt", "dataform")]
warehouse = [k for k in layers if k in ("snowflake", "bigquery", "databricks")]

if len(data_core) > 1:
    ask, opts = "dbt and Dataform at the same time: which one governs the project?", ["dbt", "dataform", "dbt,dataform"]
elif "dbt" in data_core and not warehouse:
    ask, opts = "dbt with no detectable adapter: which warehouse does it use?", ["dbt,snowflake", "dbt,bigquery", "dbt,databricks", "dbt"]
elif "dbt" in data_core and len(warehouse) > 1:
    ask, opts = f"dbt with evidence of several warehouses ({', '.join(warehouse)}): which one is the warehouse?", [f"dbt,{w}" for w in warehouse]
elif len(warehouse) > 1 and not data_core:
    ask, opts = f"Evidence of several warehouses ({', '.join(warehouse)}) without dbt/Dataform: which one applies?", warehouse + [",".join(warehouse)]
elif "dataform" in data_core and "snowflake" in warehouse:
    ask, opts = "Dataform only runs on BigQuery, but there is evidence of Snowflake: what is it?", ["dataform,bigquery", "dataform,bigquery,snowflake"]
if not layers:
    ask, opts = "Repository with no recognizable evidence: what type of project is it?", ["dbt,snowflake", "dbt,bigquery", "dbt,databricks", "dataform,bigquery", "bigquery", "databricks", "webapp", "python-lib", "generic"]

if ask:
    print(f"PROFILES={','.join(layers) or 'unknown'} CONFIDENCE=0.5 EVIDENCE={';'.join(ev)[:300] or 'none'} ASK={ask} OPTIONS={'|'.join(opts)}")
    sys.exit(2)
layers.sort(key=lambda k: ("dbt", "dataform", "snowflake", "bigquery", "databricks", "webapp", "python-lib").index(k))
top = sorted(score.values(), reverse=True)
conf = 0.9 if top[0] >= 6 else 0.8
print(f"PROFILES={','.join(layers)} CONFIDENCE={conf:.2f} EVIDENCE={';'.join(ev)[:300]}")
sys.exit(0)
