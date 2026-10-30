#!/usr/bin/env python3
"""Secret-free connection catalog for data projects: how an agent connects, per environment, without asking.

Usage: data_connect.py [--repo DIR] <command>
  init      draft .agent-memory/connections.yaml from the detected profile and non-secret project files (never overwrites)
  show      print the catalog summary
  render    write docs/agent-memory/connections.md (generated, indexed by the memory sync)
  check     which CLIs are installed and which env vars are set on THIS machine (names only, never values); no network
  brief     one-paragraph summary for the startup briefing
  discover  fill `TODO` identifiers by asking the user's own, already-authenticated CLIs (gcloud, bq, snow, databricks); never overwrites a value
  enable-live  probe each environment with a read-only metadata call and set `metadata_sync: true` where it works (retry backoff 24 h on failure)

The catalog stores system, auth METHOD, environment variable NAMES, non-secret identifiers and command templates.
Passwords, tokens and key contents are never read into it. Edit the file by hand: `TODO` marks what could not be detected.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import miniyaml  # noqa: E402

CATALOG = ".agent-memory/connections.yaml"
DOC = "docs/agent-memory/connections.md"
SAFE_PROFILE_KEYS = ("type", "account", "role", "database", "warehouse", "schema", "project", "dataset", "location", "method", "threads", "host",
                     "http_path", "catalog", "target", "connection")
SECRET_KEYS = re.compile(r"pass|secret|token|private|key|credential|pat$", re.I)
ENV_VAR = re.compile(r"""env_var\(\s*['"]([A-Z0-9_]+)['"]""")

TEMPLATES = {
    "bigquery": {
        "tools": {"bq": "install the Google Cloud SDK (https://cloud.google.com/sdk)", "gcloud": "install the Google Cloud SDK"},
        "auth": {"method": "adc", "env": ["GOOGLE_APPLICATION_CREDENTIALS"], "notes": "Prefer user ADC (`gcloud auth application-default login`); a service-account key file path may be given through the env var, never stored here."},
        "commands": {
            "validate": ["gcloud auth application-default print-access-token >/dev/null && echo auth-ok", "bq --project_id={project} ls --max_results=5"],
            "explore": ["bq --project_id={project} show --schema --format=prettyjson {project}:{dataset}.<table>", "bq --project_id={project} ls {dataset}"],
            "dry_run": ["bq --project_id={project} query --nouse_legacy_sql --dry_run '<sql>'"],
        },
        "forbidden": ["bq rm", "bq load", "bq cp", "bq update", "any DML/DDL against production"],
    },
    "snowflake": {
        "tools": {"snow": "pip install snowflake-cli  (or brew install snowflake-cli)", "dbt": "pip install dbt-snowflake"},
        "auth": {"method": "key-pair", "env": ["SNOWFLAKE_PRIVATE_KEY_PATH", "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"], "notes": "Key-pair or OAuth for service accounts; connections live in the user's own ~/.snowflake/connections.toml, never in the repo."},
        "commands": {
            "validate": ["snow connection test -c {connection}", "snow sql -c {connection} -q 'select current_role(), current_warehouse()'"],
            "explore": ["snow sql -c {connection} -q 'show tables in schema {database}.{schema}'", "snow sql -c {connection} -q 'describe table {database}.{schema}.<table>'"],
        },
        "forbidden": ["resizing or resuming warehouses", "DDL/DML against production outside the pipeline"],
    },
    "databricks": {
        "tools": {"databricks": "brew install databricks  (or pip install databricks-cli)"},
        "auth": {"method": "oauth-profile", "env": ["DATABRICKS_HOST", "DATABRICKS_CONFIG_PROFILE"], "notes": "OAuth U2M via `databricks auth login --profile <name>`; tokens live in ~/.databrickscfg, never in the repo."},
        "commands": {
            "validate": ["databricks auth profiles", "databricks bundle validate -t {target}"],
            "explore": ["databricks tables list {catalog} {schema} --output json", "databricks bundle summary -t {target}"],
        },
        "forbidden": ["databricks bundle deploy -t prod", "databricks jobs run-now on production without approval"],
    },
    "dbt": {
        "tools": {"dbt": "pip install dbt-core plus the adapter for your warehouse"},
        "auth": {"method": "profiles.yml", "env": [], "notes": "profiles.yml stays outside the repo (~/.dbt/profiles.yml) and is never read for secrets."},
        "commands": {
            "validate": ["dbt debug --target {target}", "dbt parse --target {target}"],
            "explore": ["dbt ls --resource-type model --output json --target {target}", "dbt compile --select <model> --target {target}", "dbt show --select <model> --limit 20 --target {target}"],
            "run": ["dbt build --select <model>+ --target {target}   # dev only; prod needs approval"],
        },
        "forbidden": ["dbt run/build/seed/snapshot --target prod without approval", "--full-refresh on large tables without approval"],
    },
    "dataform": {
        "tools": {"dataform": "npm i -g @dataform/cli"},
        "auth": {"method": "adc", "env": [], "notes": "BigQuery credentials come from ADC; `.df-credentials.json` is local-only and never committed."},
        "commands": {
            "validate": ["dataform compile", "dataform run --dry-run"],
            "explore": ["dataform compile --json", "dataform run --dry-run --actions <action>"],
        },
        "forbidden": ["dataform run against production without approval", "rescheduling production workflows"],
    },
}


def load(repo: Path) -> dict:
    p = repo / CATALOG
    return (miniyaml.load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}


def layers_of(repo: Path) -> list[str]:
    pj = repo / ".agent-memory" / "project.yaml"
    if pj.exists():
        m = re.search(r"^profile:\s*([\w,\-]+)", pj.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).split(",")
    out = []
    if list(repo.rglob("dbt_project.yml"))[:1]: out.append("dbt")
    if list(repo.rglob("workflow_settings.yaml"))[:1] or list(repo.rglob("dataform.json"))[:1]: out += ["dataform", "bigquery"]
    if list(repo.rglob("databricks.yml"))[:1]: out.append("databricks")
    return out


def warehouse_of(layers: list[str]) -> str:
    return next((w for w in ("bigquery", "snowflake", "databricks") if w in layers), "")


def dbt_targets(repo: Path) -> tuple[str, dict]:
    pf = next(iter(sorted(repo.rglob("dbt_project.yml"), key=lambda p: len(p.parts))), None)
    prof_name = (miniyaml.load(pf.read_text(encoding="utf-8", errors="ignore")) or {}).get("profile", "") if pf else ""
    out: dict = {}
    for cand in (repo / "profiles.yml", pf.parent / "profiles.yml" if pf else None, Path.home() / ".dbt" / "profiles.yml"):
        if cand and cand.exists():
            y = miniyaml.load(cand.read_text(encoding="utf-8", errors="ignore")) or {}
            prof = y.get(prof_name) or {}
            for tname, t in (prof.get("outputs") or {}).items():
                if not isinstance(t, dict):
                    continue
                safe = {k: str(v) for k, v in t.items() if k in SAFE_PROFILE_KEYS and v is not None and "{{" not in str(v) and "⟦" not in str(v)}
                envs = sorted({e for v in t.values() if isinstance(v, str) for e in ENV_VAR.findall(v.replace("⟦", "{{").replace("⟧", "}}"))})
                secrets = sorted(k for k in t if SECRET_KEYS.search(k) and k not in ("method",))
                out[tname] = {"safe": safe, "env": envs, "secret_keys": secrets, "default": tname == prof.get("target")}
            if out:
                break
    return prof_name, out


def draft(repo: Path) -> dict:
    layers = layers_of(repo)
    envs: dict = {}
    wh = warehouse_of(layers)
    if "dbt" in layers:
        prof, targets = dbt_targets(repo)
        for tname, t in (targets or {"dev": {"safe": {}, "env": [], "secret_keys": [], "default": True}, "prod": {"safe": {}, "env": [], "secret_keys": [], "default": False}}).items():
            s = t["safe"]
            tw = s.get("type", wh)
            ids = {"target": tname, **{k: v for k, v in s.items() if k not in ("type", "threads")}}
            if tw == "bigquery":
                ids = {"target": tname, "project": s.get("project", "TODO"), "datasets": [s.get("dataset", s.get("schema", "TODO"))], "location": s.get("location", "TODO")}
            envs[tname] = {"role": "production" if re.search(r"prod|prd", tname, re.I) else "development", "system": "dbt", "warehouse": tw or "TODO",
                           "identifiers": ids, "auth_env": t["env"], "auth_secret_settings_present": t["secret_keys"], "metadata_sync": False}
    elif "dataform" in layers:
        wsf = next(iter(repo.rglob("workflow_settings.yaml")), None)
        ws = (miniyaml.load(wsf.read_text(encoding="utf-8")) or {}) if wsf else {}
        for tname in ("dev", "prod"):
            envs[tname] = {"role": "production" if tname == "prod" else "development", "system": "dataform", "warehouse": "bigquery",
                           "identifiers": {"project": ws.get("defaultProject", "TODO"), "datasets": [ws.get("defaultDataset", "TODO")], "location": ws.get("defaultLocation", "TODO")},
                           "metadata_sync": False}
    elif "databricks" in layers:
        bf = next(iter(repo.rglob("databricks.yml")), None)
        y = (miniyaml.load(bf.read_text(encoding="utf-8")) or {}) if bf else {}
        for tname, t in (y.get("targets") or {"dev": {}, "prod": {}}).items():
            envs[tname] = {"role": "production" if (isinstance(t, dict) and t.get("mode") == "production") or re.search(r"prod", tname) else "development", "system": "databricks", "warehouse": "databricks",
                           "identifiers": {"target": tname, "host": ((t or {}).get("workspace") or {}).get("host", "TODO") if isinstance(t, dict) else "TODO", "catalog": "TODO", "schemas": ["TODO"], "profile": "TODO"},
                           "metadata_sync": False}
    else:
        for w in [x for x in layers if x in ("bigquery", "snowflake", "databricks")] or ["TODO"]:
            envs["dev"] = {"role": "development", "system": w, "warehouse": w, "identifiers": {}, "metadata_sync": False}
    return {"schema_version": 1, "layers": layers, "environments": envs}


def q(v) -> str:
    s = str(v)
    return '"' + s.replace("\\", "\\\\").replace('"', "'") + '"' if re.search(r"[:#\[\]{},&*!|>%@`]|^\s|\s$|^$", s) or s in ("true", "false", "null") else s


def emit(cat: dict) -> str:
    L = ["# Connection catalog. NO SECRETS: only method, env var NAMES, non-secret identifiers and command templates.",
         "# Edit by hand; `TODO` = could not be detected. `metadata_sync: true` lets Timewarden read table/column metadata (read-only) from that environment.",
         f"schema_version: {cat['schema_version']}", f"layers: [{', '.join(cat['layers'])}]", "environments:"]
    for name, e in cat["environments"].items():
        L += [f"  {name}:", f"    role: {e['role']}", f"    system: {e['system']}", f"    warehouse: {e['warehouse']}", "    identifiers:"]
        for k, v in (e.get("identifiers") or {}).items():
            L.append(f"      {k}: [{', '.join(q(x) for x in v)}]" if isinstance(v, list) else f"      {k}: {q(v)}")
        if not e.get("identifiers"):
            L[-1] = "    identifiers: {}"
        if e.get("auth_env"):
            L.append(f"    auth_env: [{', '.join(e['auth_env'])}]")
        if e.get("auth_secret_settings_present"):
            L.append(f"    auth_secret_settings_present: [{', '.join(e['auth_secret_settings_present'])}]   # names only; values are never read")
        L.append(f"    metadata_sync: {'true' if e.get('metadata_sync') else 'false'}")
    return "\n".join(L) + "\n"


def recipe(env_name: str, e: dict) -> dict:
    """Merge template(s) for the environment's tool + warehouse, substituting identifiers."""
    ids = {k: (v[0] if isinstance(v, list) and v else v) for k, v in (e.get("identifiers") or {}).items()}
    ids.setdefault("target", env_name)
    keys = [k for k in (e.get("system"), e.get("warehouse")) if k in TEMPLATES]
    out = {"tools": {}, "commands": {}, "forbidden": [], "auth": None}
    def sub(s):
        return re.sub(r"\{(\w+)\}", lambda m: str(ids.get(m.group(1), m.group(0))), s)
    wh = e.get("warehouse")
    for k in dict.fromkeys(keys):
        t = TEMPLATES[k]
        out["tools"].update(t["tools"]); out["forbidden"] += t["forbidden"]
        for c, lst in t["commands"].items():
            out["commands"].setdefault(c, []).extend(sub(x) for x in lst)
    out["auth"] = (TEMPLATES.get(wh) or TEMPLATES.get(e.get("system")) or {}).get("auth")
    return out


def render(repo: Path) -> str:
    cat = load(repo)
    L = ["---\nid: data-connections\ntype: runbook\nstatus: verified\ngenerated: true\nsource_paths: [.agent-memory/connections.yaml]\n---\n# How to connect (per environment)\n",
         "Generated from `.agent-memory/connections.yaml` by `data_connect.py render`. Contains no secrets. Read this before asking the user how to connect.\n"]
    for name, e in (cat.get("environments") or {}).items():
        r = recipe(name, e)
        ids = ", ".join(f"{k}={v}" for k, v in (e.get("identifiers") or {}).items())
        L.append(f"\n## Environment `{name}` ({e.get('role', '?')}, {e.get('system', '?')} on {e.get('warehouse', '?')})\n")
        L.append(f"Identifiers: {ids or 'none recorded'}.\n")
        if r["auth"]:
            envs = e.get("auth_env") or r["auth"]["env"]
            L.append(f"Authentication: {r['auth']['method']}. Environment variables used (names only): {', '.join(envs) if envs else 'none'}. {r['auth']['notes']}\n")
        if r["tools"]:
            L.append("Required tools: " + "; ".join(f"`{t}` ({h})" for t, h in r["tools"].items()) + ".\n")
        for c, lst in r["commands"].items():
            L.append(f"\n{c.replace('_', ' ').capitalize()} commands:\n" + "".join(f"- `{x}`\n" for x in lst))
        forb = r["forbidden"] + (["any write or run against this environment without explicit approval"] if e.get("role") == "production" else [])
        if forb:
            L.append("\nNever without explicit approval: " + "; ".join(forb) + ".\n")
        if e.get("metadata_sync"):
            L.append("\nMetadata sync is ON for this environment (read-only table/column metadata is mirrored into the data graph).\n")
    return "".join(L)


def check(repo: Path) -> int:
    cat = load(repo)
    print(f"host: {platform.system()} {platform.machine()} ({platform.platform(terse=True)}); python {platform.python_version()}")
    if not cat.get("environments"):
        print("no catalog yet: run `data_connect.py init`"); return 1
    missing = 0
    for name, e in cat["environments"].items():
        r = recipe(name, e)
        envs = list(dict.fromkeys((e.get("auth_env") or []) + ((r["auth"] or {}).get("env") or [])))
        print(f"[{name}] role={e.get('role')} system={e.get('system')}/{e.get('warehouse')} metadata_sync={bool(e.get('metadata_sync'))}")
        for t, hint in r["tools"].items():
            ok = shutil.which(t) is not None
            missing += not ok
            print(f"    tool {t}: {'installed' if ok else 'MISSING -> ' + hint}")
        for v in envs:
            print(f"    env  {v}: {'set' if os.environ.get(v) else 'unset'}")
        todo = [k for k, v in (e.get("identifiers") or {}).items() if "TODO" in str(v)]
        if todo:
            print(f"    TODO identifiers: {', '.join(todo)}")
    return 0


def brief(repo: Path, lang: str = "en") -> str:
    cat = load(repo)
    if not cat.get("environments"):
        return ""
    miss, todo = set(), 0
    parts = []
    for name, e in cat["environments"].items():
        r = recipe(name, e)
        miss |= {t for t in r["tools"] if shutil.which(t) is None}
        todo += sum(1 for v in (e.get("identifiers") or {}).values() if "TODO" in str(v))
        parts.append(f"{name} ({'prod' if str(e.get('role', '')).startswith('prod') else 'dev'}, {e.get('warehouse', '?')})")
    s = f"Connections: {', '.join(parts)}. Recipes: docs/agent-memory/connections.md (do not ask the user how to connect; run `data_connect.py check` to see this machine's tools)."
    if miss:
        s += f" Missing tools here: {', '.join(sorted(miss))}."
    if todo:
        s += f" {todo} identifier(s) still TODO in {CATALOG}."
    return s


def edit_env(text: str, env: str, key: str, value: str) -> tuple[str, bool]:
    """Set `key: value` inside one environment block with a targeted line edit; inserts under `identifiers:` if the key is absent."""
    lines, out, in_env, done = text.split("\n"), [], False, False
    for ln in lines:
        m = re.match(r"^  (\S+):\s*$", ln)
        if m:
            in_env = m.group(1) == env
        if in_env and not done and re.match(rf"^\s+{re.escape(key)}:", ln):
            out.append(re.match(r"^(\s+)", ln).group(1) + f"{key}: {value}"); done = True; continue
        out.append(ln)
    if not done:
        out2, in_env = [], False
        for ln in out:
            m = re.match(r"^  (\S+):\s*$", ln)
            if m:
                in_env = m.group(1) == env
            if in_env and not done and re.match(r"^\s+identifiers:", ln):
                out2.append("    identifiers:" if ln.rstrip().endswith("{}") else ln)
                out2.append(f"      {key}: {value}"); done = True; continue
            out2.append(ln)
        out = out2
    return "\n".join(out), done


def _fmt(v) -> str:
    return f"[{', '.join(q(x) for x in v)}]" if isinstance(v, list) else q(v)


def _first(out: str):
    try:
        return json.loads(out)
    except ValueError:
        return None


def discover(repo: Path, run) -> list[str]:
    """Fill missing/TODO identifiers from the user's authenticated CLIs. Metadata only; each call is best-effort."""
    p = repo / CATALOG
    if not p.exists():
        return []
    text, cat, notes = p.read_text(encoding="utf-8"), load(repo), []
    def todo(v):
        return v in (None, "", [], ["TODO"]) or "TODO" in str(v)
    for name, e in (cat.get("environments") or {}).items():
        ids = e.get("identifiers") or {}
        w = str(e.get("warehouse") or "").lower()
        upd: dict = {}
        try:
            if "bigquery" in w:
                if todo(ids.get("project")):
                    pr = run(["gcloud", "config", "get-value", "project"], 20).strip()
                    if pr and pr != "(unset)" and " " not in pr:
                        upd["project"] = pr
                proj, dsets = upd.get("project") or ids.get("project"), ids.get("datasets") or ids.get("dataset")
                if not todo(proj) and not todo(dsets) and todo(ids.get("location")):
                    d0 = dsets[0] if isinstance(dsets, list) else dsets
                    info = _first(run(["bq", "show", "--format=json", f"{proj}:{d0}"], 30))
                    if isinstance(info, dict) and info.get("location"):
                        upd["location"] = info["location"]
            elif "snowflake" in w and todo(ids.get("connection")):
                conns = _first(run(["snow", "connection", "list", "--format", "json"], 30)) or []
                pick = next((c for c in conns if c.get("is_default")), conns[0] if conns else None)
                if pick:
                    upd["connection"] = pick.get("connection_name") or pick.get("name")
            elif "databricks" in w:
                if todo(ids.get("profile")):
                    profs = _first(run(["databricks", "auth", "profiles", "--output", "json"], 30)) or {}
                    plist = profs.get("profiles", profs) if isinstance(profs, dict) else profs
                    good = [x for x in plist if x.get("valid")] or plist
                    if good:
                        upd["profile"] = good[0]["name"]
                prof = upd.get("profile") or ids.get("profile")
                base = ["databricks"] + (["--profile", prof] if not todo(prof) else [])
                if todo(ids.get("catalog")) and not todo(prof):
                    cats = _first(run(base + ["catalogs", "list", "--output", "json"], 30)) or []
                    user = [c["name"] for c in cats if c.get("name") not in ("system", "samples", "hive_metastore", "__databricks_internal") and c.get("catalog_type", "") != "SYSTEM_CATALOG"]
                    if len(user) == 1:
                        upd["catalog"] = user[0]
                cat_ = upd.get("catalog") or ids.get("catalog")
                if todo(ids.get("schemas")) and not todo(prof) and not todo(cat_):
                    sch = _first(run(base + ["schemas", "list", cat_, "--output", "json"], 30)) or []
                    names = [x["name"] for x in sch if x.get("name") not in ("information_schema", "default")]
                    if names:
                        upd["schemas"] = names[:12]
        except Exception as exc:   # LiveError or JSON shape: discovery is best-effort and never fatal
            notes.append(f"[{name}] discovery incomplete: {str(exc)[:120]}")
        for k, v in upd.items():
            text, ok = edit_env(text, name, k, _fmt(v))
            if ok:
                notes.append(f"[{name}] {k} = {v if not isinstance(v, list) else ', '.join(v)}")
    if any("=" in n for n in notes):
        p.write_text(text, encoding="utf-8")
    return notes


def enable_live(repo: Path, probe, backoff_hours: float = 24) -> list[str]:
    """Probe each not-yet-enabled environment (read-only signature call) and flip metadata_sync on success."""
    import time
    p = repo / CATALOG
    if not p.exists():
        return []
    sdir = repo / ".agent-memory" / "data-sync-state"
    sdir.mkdir(parents=True, exist_ok=True)
    pf = sdir / "probe.json"
    state = json.loads(pf.read_text()) if pf.exists() else {}
    text, notes = p.read_text(encoding="utf-8"), []
    for name, e in (load(repo).get("environments") or {}).items():
        if e.get("metadata_sync") is True:
            continue
        if time.time() - state.get(name, {}).get("at", 0) < backoff_hours * 3600:
            continue
        res = probe(e)   # returns (ok, message)
        state[name] = {"at": time.time(), "ok": res[0], "message": res[1][:160]}
        if res[0]:
            text, _ = edit_env(text, name, "metadata_sync", "true")
            notes.append(f"[{name}] live metadata enabled")
        else:
            notes.append(f"[{name}] live metadata not enabled: {res[1][:120]}")
    if any("enabled" in n and "not enabled" not in n for n in notes):
        p.write_text(text, encoding="utf-8")
    pf.write_text(json.dumps(state, indent=1, sort_keys=True))
    return notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("cmd", choices=("init", "show", "render", "check", "brief", "discover", "enable-live"))
    a = ap.parse_args()
    repo = a.repo.resolve()
    if a.cmd == "init":
        p = repo / CATALOG
        if p.exists():
            print(f"exists, left untouched: {CATALOG}")
        else:
            d = draft(repo)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(emit(d), encoding="utf-8")
            print(f"created: {CATALOG} ({len(d['environments'])} environment(s): {', '.join(d['environments'])}). Review the TODOs.")
        out = repo / DOC
        out.parent.mkdir(parents=True, exist_ok=True)
        txt = render(repo)
        if not out.exists() or out.read_text() != txt:
            out.write_text(txt, encoding="utf-8")
        return 0
    if a.cmd == "render":
        out = repo / DOC
        out.parent.mkdir(parents=True, exist_ok=True)
        txt = render(repo)
        if not out.exists() or out.read_text() != txt:
            out.write_text(txt, encoding="utf-8"); print(f"updated: {DOC}")
        else:
            print(f"unchanged: {DOC}")
        return 0
    if a.cmd == "show":
        print((repo / CATALOG).read_text() if (repo / CATALOG).exists() else "no catalog"); return 0
    if a.cmd in ("discover", "enable-live"):
        import data_sources as dsrc
        if a.cmd == "discover":
            notes = discover(repo, dsrc.RUN)
        else:
            def probe(env):
                ad = dsrc.adapter_for(env)
                if not ad:
                    return False, f"no live adapter for {env.get('warehouse')}"
                miss = dsrc.required_ids(env)
                if miss:
                    return False, "identifiers still missing: " + ", ".join(miss)
                try:
                    return True, "signature " + ad[0](env)[:60]
                except dsrc.LiveError as exc:
                    return False, str(exc)
            notes = enable_live(repo, probe)
        txt = render(repo)
        out = repo / DOC
        if out.exists() and out.read_text() != txt:
            out.write_text(txt, encoding="utf-8")
        print("\n".join(notes) or "nothing to do")
        return 0
    if a.cmd == "brief":
        print(brief(repo)); return 0
    return check(repo)


if __name__ == "__main__":
    sys.exit(main())
