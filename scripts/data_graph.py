#!/usr/bin/env python3
"""Lineage graph of a data repository (dbt, Dataform, Databricks). Offline, deterministic, no credentials.

Usage: data_graph.py [--repo DIR] <command> [args]
  build [--tools auto|run|off] [--no-docs]   scan the repo and write graph.json + generated documents
  status                                     graph age/size and whether the sources changed since the build
  find <text>                                nodes whose name or path contains the text
  show <node>                                one node: kind, path, columns, tests, direct deps and consumers
  upstream <node> [--depth N]                everything the node depends on
  downstream <node> [--depth N]              everything that depends on the node
  impact <node>                              downstream grouped by depth (what breaks if this changes)
  path <from> <to>                           shortest dependency path
  check [--json]                             cycles, unresolved/dynamic refs, layer skips, orphans, coverage, live drift
Add --json to find/show/upstream/downstream/impact for machine output.

Sources, in order of fidelity: the tool's own offline export when available (dbt manifest.json / `dbt parse`,
`dataform compile --json`) and the built-in static parser otherwise. Live-system metadata (opt-in) is merged from
.agent-memory/data-sync-state/live.json, written by data_sync.py. Output is byte-stable when nothing changed.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import miniyaml  # noqa: E402

SCHEMA = 1
SKIP_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__", "target", "dbt_packages", "dbt_modules", ".terraform",
             "dist", "build", "logs", ".next", ".databricks", ".claude", ".agent-memory"}
SECRET_FILE = re.compile(r"(^|/)(profiles\.ya?ml|\.env.*|\.databrickscfg|.*service-account.*\.json|.*-sa\.json|\.df-credentials\.json|"
                         r".*\.(p8|pem|key|pfx)|connections\.toml)$", re.I)
OUT_REL = "docs/agent-memory/data-graph"
CARD_CAP = 11000     # characters per generated card document (keeps Cognee chunks coherent)
SOURCE_EXT = {".sql", ".sqlx", ".js", ".yml", ".yaml", ".py", ".json"}
MODEL_KINDS = {"model", "table", "view", "incremental", "snapshot", "seed"}


# ----------------------------------------------------------------------------- files
def iter_files(root: Path, exts=None, extra_skip=()):
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS and d not in extra_skip and not d.startswith(".git"))
        for f in sorted(fns):
            p = Path(dp) / f
            rel = p.relative_to(root).as_posix()
            if SECRET_FILE.search(rel) or (exts and p.suffix.lower() not in exts):
                continue
            yield p


def read(p: Path, cap=400_000) -> str:
    try:
        if p.stat().st_size > 2_000_000:
            return ""
        return p.read_text(encoding="utf-8", errors="ignore")[:cap]
    except OSError:
        return ""


def yload(p: Path):
    return miniyaml.load(read(p)) or {}


def fingerprint(repo: Path) -> str:
    """Content hash of every file that can change the graph. Cheap and independent of mtimes."""
    h = hashlib.sha256()
    for p in iter_files(repo, SOURCE_EXT):
        rel = p.relative_to(repo).as_posix()
        if rel.startswith(OUT_REL) or rel.startswith("openspec/") or rel.startswith("docs/"):
            continue
        if p.suffix == ".json" and p.name not in ("dataform.json", "package.json"):
            continue
        h.update(rel.encode()); h.update(b"\0")
        try:
            h.update(hashlib.sha1(p.read_bytes()).digest())
        except OSError:
            pass
    return h.hexdigest()[:20]


# ----------------------------------------------------------------------------- graph model
class Graph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: set[tuple[str, str, str]] = set()
        self.pending: list[tuple[str, str, str, str]] = []   # (src, name, kind_hint, edge_type)
        self.meta: dict = {"systems": [], "sources": {}}

    def node(self, nid: str, kind: str, name: str, **kw) -> dict:
        n = self.nodes.setdefault(nid, {"id": nid, "name": name, "kind": kind, "system": kw.pop("system", ""), "path": "", "folder": "",
                                        "schema": "", "database": "", "materialization": "", "tags": [], "description": "", "columns": [],
                                        "tests": [], "source": "static", "declared": True})
        for k, v in kw.items():
            if v not in (None, "", [], {}):
                n[k] = v
        return n

    def edge(self, src: str, dst: str, typ: str = "depends_on"):
        if src != dst:
            self.edges.add((src, dst, typ))

    def ref(self, src: str, name: str, hint: str = "", typ: str = "depends_on"):
        self.pending.append((src, name, hint, typ))

    def resolve(self):
        byname: dict[str, list[str]] = collections.defaultdict(list)
        for nid, n in self.nodes.items():
            if n["kind"] not in ("exposure", "job", "pipeline", "code", "missing"):
                byname[n["name"].lower()].append(nid)
        for src, name, hint, typ in self.pending:
            cands = byname.get(name.lower(), [])
            if hint:
                c2 = [c for c in cands if self.nodes[c]["kind"] in hint.split("|")]
                cands = c2 or cands
            if cands:
                self.edge(src, sorted(cands)[0], typ)
            else:
                mid = f"missing:{name}"
                self.node(mid, "missing", name, declared=False, system=self.nodes[src].get("system", ""))
                self.edge(src, mid, typ)
        self.pending = []

    def to_json(self) -> dict:
        return {"schema": SCHEMA, "systems": sorted(set(self.meta["systems"])), "sources": self.meta["sources"],
                "nodes": [self.nodes[k] for k in sorted(self.nodes)], "edges": [list(e) for e in sorted(self.edges)]}


def shape(n: dict) -> dict:
    for k in ("tags",):
        n[k] = sorted(set(n[k]))
    return n


def top_folder(rel_dir: str) -> str:
    return rel_dir.split("/")[0] if rel_dir and rel_dir != "." else "(root)"


# ----------------------------------------------------------------------------- dbt
def _balanced(text: str, start: int) -> str:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
    return ""


REF_RE = re.compile(r"""\bref\(\s*(['"])(.+?)\1\s*(?:,\s*(['"])(.+?)\3)?""")
SRC_RE = re.compile(r"""\bsource\(\s*['"](.+?)['"]\s*,\s*['"](.+?)['"]\s*\)""")
DYN_REF_RE = re.compile(r"""\bref\(\s*[^'"\s)]""")


def _flatten_folder_cfg(d, prefix="", out=None):
    out = {} if out is None else out
    if isinstance(d, dict):
        own = {k.lstrip("+"): v for k, v in d.items() if k.startswith("+") or not isinstance(v, dict)}
        if own:
            out[prefix] = own
        for k, v in d.items():
            if not k.startswith("+") and isinstance(v, dict):
                _flatten_folder_cfg(v, f"{prefix}/{k}".strip("/"), out)
    return out


def _folder_default(rel_dir: str, fcfg: dict, key: str):
    best = None
    for pre, cfg in fcfg.items():
        if (pre == "" or rel_dir == pre or rel_dir.startswith(pre + "/")) and key in cfg:
            if best is None or len(pre) >= len(best[0]):
                best = (pre, cfg[key])
    return best[1] if best else None


def _tests_of(entry) -> list[str]:
    out = []
    for t in (entry or []):
        out.append(t if isinstance(t, str) else (next(iter(t)) if isinstance(t, dict) and t else "test"))
    return out


def scan_dbt(repo: Path, g: Graph, use_manifest: bool):
    pf = sorted(repo.rglob("dbt_project.yml"), key=lambda p: len(p.parts))
    pf = [p for p in pf if not any(x in SKIP_DIRS for x in p.relative_to(repo).parts)]
    if not pf:
        return
    root = pf[0].parent
    cfg = yload(pf[0])
    pname = str(cfg.get("name", "project"))
    g.meta["systems"].append("dbt")
    g.meta["sources"]["dbt"] = {"project": pname, "root": root.relative_to(repo).as_posix() or "."}
    if use_manifest and _scan_manifest(repo, root, g, pname):
        return
    g.meta["sources"]["dbt"]["tier"] = "static"
    mpaths = cfg.get("model-paths") or cfg.get("source-paths") or ["models"]
    spaths = cfg.get("seed-paths") or cfg.get("data-paths") or ["seeds"]
    snpaths = cfg.get("snapshot-paths") or ["snapshots"]
    fcfg = _flatten_folder_cfg((cfg.get("models") or {}).get(pname, {}) if isinstance(cfg.get("models"), dict) else {})
    if isinstance(cfg.get("models"), dict):
        top = {k: v for k, v in cfg["models"].items() if k.startswith("+")}
        if top:
            fcfg.setdefault("", {}).update({k.lstrip("+"): v for k, v in top.items()})
    for kind, paths in (("model", mpaths), ("seed", spaths), ("snapshot", snpaths)):
        for sp in paths:
            base = root / sp
            if not base.is_dir():
                continue
            for p in iter_files(base, {".sql", ".csv"}):
                rel_in = p.relative_to(base).parent.as_posix()
                rel = p.relative_to(repo).as_posix()
                if kind == "seed":
                    if p.suffix == ".csv":
                        g.node(f"seed:{p.stem}", "seed", p.stem, system="dbt", path=rel, folder=top_folder(rel_in), materialization="seed")
                    continue
                if p.suffix != ".sql":
                    continue
                text = re.sub(r"\{#.*?#\}", "", read(p), flags=re.S)
                snaps = re.findall(r"\{%-?\s*snapshot\s+(\w+)\s*-?%\}", text)
                names = snaps if (kind == "snapshot" and snaps) else [p.stem]
                for nm in names:
                    k = "snapshot" if (kind == "snapshot" or snaps) else "model"
                    nid = f"{k}:{nm}"
                    mat = None
                    tags: list[str] = []
                    schema = ""
                    m = re.search(r"\bconfig\s*\(", text)
                    flags = {}
                    if m:
                        args = _balanced(text, m.end() - 1)
                        mm = re.search(r"materialized\s*=\s*['\"](\w+)['\"]", args)
                        mat = mm.group(1) if mm else None
                        tm = re.search(r"tags\s*=\s*(\[[^\]]*\]|['\"][^'\"]+['\"])", args)
                        if tm:
                            tags = re.findall(r"['\"]([^'\"]+)['\"]", tm.group(1))
                        sm = re.search(r"\bschema\s*=\s*['\"]([^'\"]+)['\"]", args)
                        schema = sm.group(1) if sm else ""
                        if re.search(r"enabled\s*=\s*false", args, re.I):
                            flags["disabled"] = True
                        for key in ("unique_key", "partition_by", "cluster_by", "incremental_strategy"):
                            if re.search(rf"\b{key}\s*=", args):
                                flags[key] = True
                    mat = mat or _folder_default(rel_in, fcfg, "materialized") or ("snapshot" if k == "snapshot" else "view")
                    ftags = _folder_default(rel_in, fcfg, "tags")
                    if ftags:
                        tags += ftags if isinstance(ftags, list) else [ftags]
                    node = g.node(nid, k, nm, system="dbt", path=rel, folder=top_folder(rel_in), materialization=mat, tags=tags,
                                  schema=schema or (_folder_default(rel_in, fcfg, "schema") or ""))
                    node.update({k2: v for k2, v in flags.items()})
                    for x in REF_RE.findall(text):
                        g.ref(nid, x[3] or x[1], "model|seed|snapshot")
                    for s, t in SRC_RE.findall(text):
                        g.ref(nid, f"{s}.{t}", "source")
                    if DYN_REF_RE.search(text):
                        node["dynamic"] = True
    _dbt_properties(repo, root, g, mpaths + spaths + snpaths)


def _dbt_properties(repo: Path, root: Path, g: Graph, paths):
    for sp in paths:
        base = root / sp
        if not base.is_dir():
            continue
        for p in iter_files(base, {".yml", ".yaml"}):
            y = yload(p)
            if not isinstance(y, dict):
                continue
            for key, kind in (("models", "model"), ("seeds", "seed"), ("snapshots", "snapshot")):
                for e in (y.get(key) or []):
                    if not isinstance(e, dict) or "name" not in e:
                        continue
                    n = g.nodes.get(f"{kind}:{e['name']}")
                    if not n:
                        continue
                    n["description"] = str(e.get("description") or n["description"] or "").strip()
                    n["tests"] = sorted(set(n["tests"] + _tests_of(e.get("tests") or e.get("data_tests"))))
                    cfgm = e.get("config") or {}
                    if isinstance(cfgm, dict) and cfgm.get("materialized") and n["materialization"] in ("", "view"):
                        n["materialization"] = cfgm["materialized"]
                    cols = []
                    for c in (e.get("columns") or []):
                        if isinstance(c, dict) and "name" in c:
                            ct = _tests_of(c.get("tests") or c.get("data_tests"))
                            cols.append({"name": str(c["name"]), "description": str(c.get("description") or "").strip(), "tests": sorted(set(ct))})
                            for t in (c.get("tests") or c.get("data_tests") or []):
                                if isinstance(t, dict) and "relationships" in t and isinstance(t["relationships"], dict):
                                    mref = REF_RE.search(str(t["relationships"].get("to", "")))
                                    if mref:
                                        g.ref(f"{kind}:{e['name']}", mref.group(4) or mref.group(2), "model|seed|snapshot", "relates")
                            n["tests"] = sorted(set(n["tests"] + ct))
                    if cols:
                        n["columns"] = cols
            for s in (y.get("sources") or []):
                if not isinstance(s, dict) or "name" not in s:
                    continue
                for t in (s.get("tables") or []):
                    if not isinstance(t, dict) or "name" not in t:
                        continue
                    cols = [{"name": str(c["name"]), "description": str(c.get("description") or "").strip(), "tests": _tests_of(c.get("tests") or c.get("data_tests"))}
                            for c in (t.get("columns") or []) if isinstance(c, dict) and "name" in c]
                    g.node(f"source:{s['name']}.{t['name']}", "source", f"{s['name']}.{t['name']}", system="dbt", path=p.relative_to(repo).as_posix(),
                           folder="(sources)", schema=str(s.get("schema") or s["name"]), database=str(s.get("database") or ""),
                           description=str(t.get("description") or s.get("description") or "").strip(), columns=cols, materialization="source",
                           tests=_tests_of(t.get("tests") or t.get("data_tests")))
            for e in (y.get("exposures") or []):
                if not isinstance(e, dict) or "name" not in e:
                    continue
                eid = f"exposure:{e['name']}"
                g.node(eid, "exposure", e["name"], system="dbt", path=p.relative_to(repo).as_posix(), folder="(exposures)",
                       description=str(e.get("description") or "").strip(), materialization=str(e.get("type") or "exposure"))
                for d in (e.get("depends_on") or []):
                    d = str(d)
                    for a in REF_RE.findall(d):
                        g.ref(eid, a[3] or a[1], "model|seed|snapshot")
                    for s_, t_ in SRC_RE.findall(d):
                        g.ref(eid, f"{s_}.{t_}", "source")


def _scan_manifest(repo: Path, root: Path, g: Graph, pname: str) -> bool:
    mf = root / "target" / "manifest.json"
    if not mf.exists():
        return False
    newest = max((p.stat().st_mtime for p in iter_files(root, {".sql", ".yml", ".yaml"}) if "target" not in p.parts), default=0)
    if mf.stat().st_mtime < newest:
        return False
    try:
        m = json.loads(mf.read_text())
    except (OSError, ValueError):
        return False
    ids: dict[str, str] = {}
    for uid, v in m.get("nodes", {}).items():
        rt = v.get("resource_type")
        if rt in ("model", "seed", "snapshot"):
            ids[uid] = f"{rt}:{v['name']}"
    for uid, v in m.get("sources", {}).items():
        ids[uid] = f"source:{v['source_name']}.{v['name']}"
    for uid, v in m.get("exposures", {}).items():
        ids[uid] = f"exposure:{v['name']}"
    for uid, v in m.get("nodes", {}).items():
        rt = v.get("resource_type")
        if rt == "test" and v.get("attached_node") in ids:
            n = g.node(ids[v["attached_node"]], "model", ids[v["attached_node"]].split(":", 1)[1], system="dbt")
            n["tests"] = sorted(set(n["tests"] + [v.get("test_metadata", {}).get("name") or v["name"]]))
    for uid, v in m.get("nodes", {}).items():
        if uid not in ids:
            continue
        rel = v.get("original_file_path", "")
        rp = (root / rel).relative_to(repo).as_posix() if rel else ""
        fo = top_folder(str(Path(rel).parent).split("/", 1)[1] if "/" in str(Path(rel).parent) else ".")
        n = g.node(ids[uid], v["resource_type"], v["name"], system="dbt", path=rp, folder=fo, schema=v.get("schema") or "", database=v.get("database") or "",
                   materialization=(v.get("config") or {}).get("materialized", ""), tags=list(v.get("tags") or []),
                   description=(v.get("description") or "").strip(), source="manifest")
        n["columns"] = [{"name": c, "description": (cv.get("description") or "").strip(), "tests": []} for c, cv in sorted((v.get("columns") or {}).items())]
        n["fqn"] = ".".join(x for x in (v.get("database"), v.get("schema"), v.get("alias") or v["name"]) if x).lower()
        if v.get("package_name") and v["package_name"] != pname:
            n["package"] = v["package_name"]
        for dep in (v.get("depends_on") or {}).get("nodes", []):
            if dep in ids:
                g.edge(ids[uid], ids[dep])
    for uid, v in m.get("sources", {}).items():
        rel = v.get("original_file_path", "")
        g.node(ids[uid], "source", f"{v['source_name']}.{v['name']}", system="dbt", path=(root / rel).relative_to(repo).as_posix() if rel else "",
               folder="(sources)", schema=v.get("schema") or "", database=v.get("database") or "", description=(v.get("description") or "").strip(),
               materialization="source", source="manifest",
               columns=[{"name": c, "description": (cv.get("description") or "").strip(), "tests": []} for c, cv in sorted((v.get("columns") or {}).items())])
    for uid, v in m.get("exposures", {}).items():
        n = g.node(ids[uid], "exposure", v["name"], system="dbt", folder="(exposures)", materialization=str(v.get("type") or "exposure"),
                   description=(v.get("description") or "").strip(), source="manifest")
        for dep in (v.get("depends_on") or {}).get("nodes", []):
            if dep in ids:
                g.edge(ids[uid], ids[dep])
    g.meta["sources"]["dbt"]["tier"] = "manifest"
    return True


# ----------------------------------------------------------------------------- dataform
CFG_BLOCK = re.compile(r"config\s*\{", re.S)
DF_REF = re.compile(r"""\b(?:ref|resolve)\(\s*(?:\{[^}]*name\s*:\s*['"]([^'"]+)['"][^}]*\}|(['"])(.+?)\2\s*(?:,\s*(['"])(.+?)\4)?)\s*\)""")


def _js_block(text: str, start: int) -> str:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
    return ""


def _js_val(block: str, key: str):
    m = re.search(rf"\b{key}\s*:\s*(['\"`])(.*?)\1", block, re.S)
    return m.group(2) if m else None


def scan_dataform(repo: Path, g: Graph, tools: str):
    wf = [p for p in iter_files(repo, {".yaml", ".json"}) if p.name in ("workflow_settings.yaml", "dataform.json")]
    wf.sort(key=lambda p: len(p.parts))
    if not wf:
        return
    root = wf[0].parent
    ws = yload(wf[0]) if wf[0].suffix == ".yaml" else (json.loads(read(wf[0]) or "{}") if read(wf[0]).strip() else {})
    default_schema = str(ws.get("defaultDataset") or ws.get("defaultSchema") or "")
    default_db = str(ws.get("defaultProject") or ws.get("defaultDatabase") or "")
    g.meta["systems"].append("dataform")
    g.meta["sources"]["dataform"] = {"root": root.relative_to(repo).as_posix() or ".", "default_project": default_db, "default_dataset": default_schema,
                                      "location": str(ws.get("defaultLocation") or "")}
    if tools != "off" and _dataform_compile(repo, root, g, tools):
        return
    g.meta["sources"]["dataform"]["tier"] = "static"
    defs = root / "definitions"
    for p in iter_files(defs if defs.is_dir() else root, {".sqlx", ".js"}):
        rel = p.relative_to(repo).as_posix()
        in_dir = p.relative_to(defs if defs.is_dir() else root).parent.as_posix()
        text = read(p)
        if p.suffix == ".sqlx":
            m = CFG_BLOCK.search(text)
            blk = _js_block(text, m.end() - 1) if m else ""
            typ = _js_val(blk, "type") or "table"
            name = _js_val(blk, "name") or p.stem
            schema = _js_val(blk, "schema") or default_schema
            body = text[m.end() + len(blk) + 1:] if m else text
            tm = re.search(r"tags\s*:\s*\[([^\]]*)\]", blk)
            tags = re.findall(r"['\"]([^'\"]+)['\"]", tm.group(1)) if tm else []
            nid = f"df:{schema}.{name}" if schema else f"df:{name}"
            kind = {"table": "table", "view": "view", "incremental": "incremental", "declaration": "declaration", "assertion": "assertion",
                    "operations": "operation", "operation": "operation"}.get(typ, typ)
            desc = _js_val(blk, "description") or ""
            n = g.node(nid, kind, name, system="dataform", path=rel, folder=top_folder(in_dir), schema=schema, database=_js_val(blk, "database") or default_db,
                       materialization=typ, tags=tags, description=desc.strip())
            cols = re.findall(r"columns\s*:\s*\{(.*?)\n\s*\}", blk, re.S)
            if cols:
                n["columns"] = [{"name": c, "description": "", "tests": []} for c in re.findall(r"^\s*(\w+)\s*:", cols[0], re.M)]
            if re.search(r"assertions\s*:", blk):
                n["tests"] = ["assertions"]
            for d in re.findall(r"dependencies\s*:\s*\[([^\]]*)\]", blk):
                for x in re.findall(r"['\"]([^'\"]+)['\"]", d):
                    g.ref(nid, x, "", "depends_on")
            for r in DF_REF.finditer(body):
                nm = r.group(1) or r.group(5) or r.group(3)
                g.ref(nid, nm, "", "depends_on")
            if re.search(r"\b(ref|resolve)\(\s*[^'\"{\s)]", body):
                n["dynamic"] = True
        else:
            for m in re.finditer(r"\b(?:publish|declare|assert|operate)\(\s*['\"]([^'\"]+)['\"]", text):
                nm = m.group(1)
                kind = {"declare": "declaration", "assert": "assertion", "operate": "operation"}.get(m.group(0).split("(")[0], "table")
                nid = f"df:{default_schema}.{nm}" if default_schema else f"df:{nm}"
                g.node(nid, kind, nm, system="dataform", path=rel, folder=top_folder(in_dir), schema=default_schema, database=default_db, materialization=kind)
                for r in DF_REF.finditer(text):
                    g.ref(nid, r.group(1) or r.group(5) or r.group(3), "", "depends_on")
            for m in re.finditer(r"declare\(\s*\{([^}]*)\}", text):
                nm = _js_val(m.group(1), "name")
                if nm:
                    sch = _js_val(m.group(1), "schema") or default_schema
                    g.node(f"df:{sch}.{nm}", "declaration", nm, system="dataform", path=rel, folder=top_folder(in_dir), schema=sch, materialization="declaration")


def _dataform_compile(repo: Path, root: Path, g: Graph, tools: str) -> bool:
    exe = shutil.which("dataform")
    if not exe or not (root / "node_modules").is_dir():
        return False
    try:
        r = subprocess.run([exe, "compile", "--json"], cwd=root, capture_output=True, text=True, timeout=90)
        data = json.loads(r.stdout)
    except (subprocess.SubprocessError, ValueError, OSError):
        return False
    if not isinstance(data, dict) or "tables" not in data and "declarations" not in data:
        return False
    def tid(t):
        return f"df:{t.get('schema', '')}.{t.get('name', '')}"
    def add(items, kind_default):
        for t in items or []:
            tg = t.get("target") or {}
            nid = tid(tg)
            kind = {"table": "table", "view": "view", "incremental": "incremental"}.get(t.get("type", kind_default), kind_default)
            ad = t.get("actionDescriptor") or {}
            g.node(nid, kind, tg.get("name", ""), system="dataform", path=(Path(root.relative_to(repo)) / t.get("fileName", "")).as_posix() if t.get("fileName") else "",
                   folder=top_folder(str(Path(t.get("fileName", "")).parent).replace("definitions/", "", 1)), schema=tg.get("schema", ""), database=tg.get("database", ""),
                   materialization=t.get("type", kind_default), tags=list(t.get("tags") or []), description=(ad.get("description") or "").strip(),
                   columns=[{"name": c.get("path", [""])[0], "description": (c.get("description") or "").strip(), "tests": []} for c in (ad.get("columns") or [])],
                   source="compile")
            g.nodes[nid]["fqn"] = ".".join(x for x in (tg.get("database"), tg.get("schema"), tg.get("name")) if x).lower()
            if t.get("disabled"):
                g.nodes[nid]["disabled"] = True
            for d in (t.get("dependencyTargets") or []):
                g.edge(nid, tid(d))
    add(data.get("tables"), "table")
    add(data.get("operations"), "operation")
    add(data.get("declarations"), "declaration")
    add(data.get("assertions"), "assertion")
    g.meta["sources"]["dataform"]["tier"] = "compile"
    for nid in list(g.nodes):
        g.nodes[nid].setdefault("source", "compile")
    return True


# ----------------------------------------------------------------------------- databricks
TABLE3 = r"[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*"
SQL_READ = re.compile(rf"\b(?:FROM|JOIN)\s+`?({TABLE3})`?", re.I)
SQL_WRITE = re.compile(rf"\b(?:INSERT\s+(?:INTO|OVERWRITE)(?:\s+TABLE)?|MERGE\s+INTO|CREATE\s+(?:OR\s+(?:REPLACE|REFRESH)\s+)?(?:STREAMING\s+)?(?:MATERIALIZED\s+VIEW|TABLE|VIEW)(?:\s+IF\s+NOT\s+EXISTS)?)\s+`?({TABLE3})`?", re.I)
PY_READ = re.compile(rf"""(?:spark\.(?:read\.)?table|readStream\.table)\(\s*['"]({TABLE3})['"]""")
PY_WRITE = re.compile(rf"""(?:saveAsTable|\.toTable)\(\s*['"]({TABLE3})['"]""")
DLT_DEF = re.compile(r"""@dlt\.(?:table|view)(?:\(([^)]*)\))?[ \t]*\n\s*def\s+(\w+)""")
DLT_READ = re.compile(r"""dlt\.read(?:_stream)?\(\s*['"]([^'"]+)['"]""")


def scan_databricks(repo: Path, g: Graph):
    bundles = [p for p in iter_files(repo, {".yml", ".yaml"}) if p.name in ("databricks.yml", "databricks.yaml")]
    dlt = False
    uses_dlt = lambda t: re.search(r"\bimport dlt\b|\bfrom dlt\b|\bdlt\.(?:table|view|read)", t)
    codes = [p for p in iter_files(repo, {".py", ".sql"}) if uses_dlt(read(p, 20000)) or SQL_WRITE.search(read(p, 20000)) or PY_WRITE.search(read(p, 20000))]
    if not bundles and not any(uses_dlt(read(p, 20000)) for p in codes):
        return
    g.meta["systems"].append("databricks")
    g.meta["sources"]["databricks"] = {"tier": "static"}
    resources: dict = {}
    if bundles:
        y = yload(bundles[0])
        g.meta["sources"]["databricks"].update({"bundle": (y.get("bundle") or {}).get("name", ""), "targets": sorted((y.get("targets") or {}).keys())})
        resources = dict(y.get("resources") or {})
        for inc in (y.get("include") or []):
            for p in sorted(bundles[0].parent.glob(str(inc))):
                r = (yload(p).get("resources") or {})
                for k, v in r.items():
                    resources.setdefault(k, {}).update(v if isinstance(v, dict) else {})
    unit_paths: dict[str, str] = {}
    for p in codes:
        rel = p.relative_to(repo).as_posix()
        text = read(p)
        cid = f"code:{rel}"
        reads = set(SQL_READ.findall(text)) | set(PY_READ.findall(text))
        writes = set(SQL_WRITE.findall(text)) | set(PY_WRITE.findall(text))
        dlt_units = []   # (table name, body of its function): reads are attributed per function, not per file
        defs = list(DLT_DEF.finditer(text))
        for i, m in enumerate(defs):
            nm = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", m.group(1) or "")
            body = text[m.end(): defs[i + 1].start() if i + 1 < len(defs) else len(text)]
            dlt_units.append((nm.group(1) if nm else m.group(2), body))
        if not (reads or writes or dlt_units):
            continue
        g.node(cid, "code", p.name, system="databricks", path=rel, folder=top_folder(p.parent.relative_to(repo).as_posix()), materialization="code")
        unit_paths[rel] = cid
        for t in sorted(reads):
            g.node(f"table:{t.lower()}", "table", t.lower(), system="databricks", folder="(tables)", declared=False, materialization="table")
            g.edge(cid, f"table:{t.lower()}", "reads")
        for t in sorted(writes):
            g.node(f"table:{t.lower()}", "table", t.lower(), system="databricks", folder="(tables)", materialization="table")
            g.nodes[f"table:{t.lower()}"]["declared"] = True
            g.edge(cid, f"table:{t.lower()}", "writes")
            for r in sorted(reads - {t}):
                g.edge(f"table:{t.lower()}", f"table:{r.lower()}", "derived")
        for t, body in dlt_units:
            g.node(f"table:{t}", "table", t, system="databricks", path=rel, folder="(dlt)", materialization="dlt")
            g.edge(cid, f"table:{t}", "writes")
            for r in sorted(set(PY_READ.findall(body)) | set(SQL_READ.findall(body))):
                g.node(f"table:{r.lower()}", "table", r.lower(), system="databricks", folder="(tables)", declared=False, materialization="table")
                g.edge(f"table:{t}", f"table:{r.lower()}", "derived")
            for r in sorted(set(DLT_READ.findall(body))):
                g.node(f"table:{r}", "table", r, system="databricks", folder="(dlt)", materialization="dlt", declared=False)
                g.edge(f"table:{t}", f"table:{r}", "derived")
    for key, pl in sorted((resources.get("pipelines") or {}).items()):
        pid = f"pipeline:{key}"
        g.node(pid, "pipeline", key, system="databricks", folder="(pipelines)", materialization="pipeline",
               description=f"catalog={pl.get('catalog', '')} schema={pl.get('schema', pl.get('target', ''))}".strip())
        for lib in (pl.get("libraries") or []):
            path = ((lib.get("notebook") or lib.get("file") or {}).get("path") or "").lstrip("./")
            for rel, cid in unit_paths.items():
                if path and (rel.endswith(path) or path.endswith(rel)):
                    g.edge(pid, cid, "runs")
    for key, job in sorted((resources.get("jobs") or {}).items()):
        jid = f"job:{key}"
        sched = (job.get("schedule") or {}).get("quartz_cron_expression", "")
        g.node(jid, "job", key, system="databricks", folder="(jobs)", materialization="job", description=f"schedule={sched}" if sched else "")
        for t in (job.get("tasks") or []):
            nb = ((t.get("notebook_task") or {}).get("notebook_path") or (t.get("spark_python_task") or {}).get("python_file") or "")
            for rel, cid in unit_paths.items():
                if nb and (rel.rsplit(".", 1)[0].endswith(nb.lstrip("./").rsplit(".", 1)[0]) or nb.lstrip("./") .endswith(rel)):
                    g.edge(jid, cid, "runs")
            pr = str(((t.get("pipeline_task") or {}).get("pipeline_id")) or "")
            m = re.search(r"resources\.pipelines\.(\w+)", pr)
            if m:
                g.edge(jid, f"pipeline:{m.group(1)}", "runs")


# ----------------------------------------------------------------------------- live merge
def merge_live(g: Graph, live: dict):
    """live = {"tables": [{"db","schema","name","type","columns":[{"name","type","partition":bool,"cluster":int}],"modified": str, "rows": int}], "scanned": ["db.schema"]}."""
    if not live or not live.get("tables"):
        return
    by_fqn = {n.get("fqn"): nid for nid, n in g.nodes.items() if n.get("fqn")}
    by_name: dict[str, list[str]] = collections.defaultdict(list)
    for nid, n in g.nodes.items():
        if n["kind"] in MODEL_KINDS | {"declaration", "source"}:
            by_name[n["name"].split(".")[-1].lower()].append(nid)
    seen = set()
    for t in live["tables"]:
        fqn = ".".join(x for x in (t.get("db"), t.get("schema"), t["name"]) if x).lower()
        nid = by_fqn.get(fqn)
        if not nid:
            c = [x for x in by_name.get(t["name"].lower(), []) if g.nodes[x].get("schema", "").lower() in ("", t.get("schema", "").lower())]
            nid = c[0] if len(c) == 1 else None
        if nid:
            n = g.nodes[nid]
            n["live"] = True
            n["fqn"] = fqn
        else:
            nid = f"live:{fqn}"
            n = g.node(nid, "live_table", t["name"], system="live", folder="(live only)", schema=t.get("schema", ""), database=t.get("db", ""),
                       materialization=str(t.get("type", "table")).lower(), declared=False)
            n["live"] = True
            n["fqn"] = fqn
        if t.get("columns"):
            n["columns"] = [{"name": c["name"], "description": next((o["description"] for o in n["columns"] if o["name"] == c["name"]), ""),
                             "tests": next((o["tests"] for o in n["columns"] if o["name"] == c["name"]), []), "type": c.get("type", "")} for c in t["columns"]]
        if any(c.get("partition") for c in t.get("columns", [])):
            n["partitioned_by"] = [c["name"] for c in t["columns"] if c.get("partition")]
        if any(c.get("cluster") for c in t.get("columns", [])):
            n["clustered_by"] = [c["name"] for c in sorted((c for c in t["columns"] if c.get("cluster")), key=lambda c: c["cluster"])]
        if t.get("rows") is not None:
            n["rows"] = t["rows"]
        seen.add(nid)
    scanned = {s.lower() for s in live.get("scanned", [])}
    for nid, n in g.nodes.items():
        if n["kind"] in MODEL_KINDS and n["declared"] and nid not in seen and n.get("fqn") and n["fqn"].rsplit(".", 1)[0] in scanned:
            n["live"] = False
    for edge in live.get("lineage", []):
        a = by_fqn.get(edge[0].lower()); b = by_fqn.get(edge[1].lower())
        if a and b:
            g.edge(a, b, "lineage")
    g.meta["sources"]["live"] = {"scanned": sorted(scanned)}


# ----------------------------------------------------------------------------- analysis
def adjacency(g: dict):
    down, up = collections.defaultdict(set), collections.defaultdict(set)
    for s, d, t in g["edges"]:
        if t in ("depends_on", "derived", "lineage", "reads", "runs"):
            up[s].add(d); down[d].add(s)
    return up, down


def depths(g: dict):
    up, _ = adjacency(g)
    memo, stack = {}, set()
    def d(n):
        if n in memo:
            return memo[n]
        if n in stack:
            return 0
        stack.add(n)
        memo[n] = 0 if not up[n] else 1 + max(d(x) for x in up[n])
        stack.discard(n)
        return memo[n]
    for n in [x["id"] for x in g["nodes"]]:
        d(n)
    return memo


def find_cycles(g: dict):
    up, _ = adjacency(g)
    color, cycles = {}, []
    sys.setrecursionlimit(10000)
    def dfs(n, path):
        color[n] = 1
        for m in sorted(up[n]):
            if color.get(m) == 1:
                cycles.append(path[path.index(m):] + [m] if m in path else [n, m])
            elif m not in color:
                dfs(m, path + [m])
        color[n] = 2
    for n in sorted(x["id"] for x in g["nodes"]):
        if n not in color:
            dfs(n, [n])
    return cycles[:20]


def conventions(g: dict):
    nodes = {n["id"]: n for n in g["nodes"]}
    dep = depths(g)
    up, down = adjacency(g)
    by_folder: dict[str, list[dict]] = collections.defaultdict(list)
    for n in g["nodes"]:
        if n["kind"] in MODEL_KINDS and n["declared"]:
            by_folder[n["folder"]].append(n)
    out = []
    for f, ns in sorted(by_folder.items()):
        pre = collections.Counter(re.match(r"^([a-z]+)_", n["name"].lower()).group(1) for n in ns if re.match(r"^([a-z]+)_", n["name"].lower()))
        top, cnt = (pre.most_common(1)[0] if pre else ("", 0))
        mats = collections.Counter(n["materialization"] or "?" for n in ns)
        with_src = sum(1 for n in ns if any(nodes[x]["kind"] in ("source", "declaration") for x in up[n["id"]]))
        out.append({"folder": f, "count": len(ns), "prefix": top if cnt / len(ns) >= 0.6 else "", "materializations": dict(mats.most_common()),
                    "tested_pct": round(100 * sum(1 for n in ns if n["tests"]) / len(ns)), "described_pct": round(100 * sum(1 for n in ns if n["description"]) / len(ns)),
                    "mean_depth": round(sum(dep[n["id"]] for n in ns) / len(ns), 1), "reads_sources": with_src,
                    "consumed_by_exposures": sum(1 for n in ns if any(nodes[x]["kind"] == "exposure" for x in down[n["id"]]))})
    out.sort(key=lambda c: (c["mean_depth"], c["folder"]))
    return out


def check(g: dict):
    nodes = {n["id"]: n for n in g["nodes"]}
    up, down = adjacency(g)
    conv = conventions(g)
    issues = []
    for c in find_cycles(g):
        issues.append({"type": "cycle", "detail": " -> ".join(nodes[x]["name"] for x in c)})
    for n in g["nodes"]:
        if n["kind"] == "missing":
            for s in sorted(down[n["id"]]):
                issues.append({"type": "unresolved_ref", "node": nodes[s]["name"], "detail": f"references '{n['name']}' which is not defined in the repo", "path": nodes[s]["path"]})
        if n.get("dynamic"):
            issues.append({"type": "dynamic_ref", "node": n["name"], "detail": "builds a ref dynamically; lineage may be incomplete", "path": n["path"]})
        if n["kind"] in MODEL_KINDS and n["declared"] and not up[n["id"]] and not down[n["id"]] and n["kind"] != "seed":
            issues.append({"type": "orphan", "node": n["name"], "detail": "no dependencies and no consumers", "path": n["path"]})
        if n.get("live") is False:
            issues.append({"type": "drift_declared_only", "node": n["name"], "detail": "declared in the repo but not found in the live system"})
        if n["kind"] == "live_table":
            issues.append({"type": "drift_live_only", "node": n["name"], "detail": f"exists live ({n['fqn']}) but is not declared in the repo"})
    # layer skips: folders that read sources directly although another folder is the main source reader
    srcdir = [c for c in conv if c["reads_sources"]]
    if len(srcdir) > 1:
        main = max(srcdir, key=lambda c: c["reads_sources"] / c["count"])
        for c in srcdir:
            if c is not main and c["reads_sources"] / c["count"] < 0.5 * (main["reads_sources"] / main["count"]) and c["mean_depth"] > main["mean_depth"]:
                for n in g["nodes"]:
                    if n["folder"] == c["folder"] and n["kind"] in MODEL_KINDS and any(nodes[x]["kind"] in ("source", "declaration") for x in up[n["id"]]):
                        issues.append({"type": "layer_skip", "node": n["name"], "detail": f"reads a source directly although '{main['folder']}' is the layer that normally reads sources", "path": n["path"]})
    untested = [n["name"] for n in g["nodes"] if n["kind"] in ("model", "table", "view", "incremental") and n["declared"] and not n["tests"]]
    nodesc = [n["name"] for n in g["nodes"] if n["kind"] in MODEL_KINDS and n["declared"] and not n["description"]]
    return {"issues": issues, "untested": untested, "undocumented": nodesc, "conventions": conv}


# ----------------------------------------------------------------------------- documents
def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "root"


def fm(doc_id: str, title: str, paths: list[str]) -> str:
    return (f"---\nid: {doc_id}\ntype: data-graph\nstatus: verified\ngenerated: true\nsource_paths: [{', '.join(paths[:6])}]\n---\n# {title}\n\n")


def render_docs(g: dict) -> dict[str, str]:
    nodes = {n["id"]: n for n in g["nodes"]}
    up, down = adjacency(g)
    chk = check(g)
    docs: dict[str, str] = {}
    kinds = collections.Counter(n["kind"] for n in g["nodes"] if n["declared"])
    ov = [fm("data-graph-overview", "Data project graph: overview", ["docs/agent-memory/data-graph/graph.json"]),
          "Generated from the repository by `scripts/data_graph.py` (do not edit; human rules go in `rules.md`). "
          "Exact queries: `python3 -I <MS>/scripts/data_graph.py upstream|downstream|impact|show <node>`.\n\n",
          f"Systems: {', '.join(g['systems']) or 'none'}. Source tier: " + ", ".join(f"{k}={v.get('tier', '?')}" for k, v in g["sources"].items() if isinstance(v, dict) and 'tier' in v) + ".\n\n",
          "Declared objects: " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())) + f". Dependencies: {len(g['edges'])}.\n\n",
          "## Observed conventions (inferred, not rules)\n\n"]
    for c in chk["conventions"]:
        ov.append(f"- Folder `{c['folder']}`: {c['count']} objects, " + (f"name prefix `{c['prefix']}_`, " if c["prefix"] else "no consistent name prefix, ") +
                  "materialization " + ", ".join(f"{k}={v}" for k, v in c["materializations"].items()) +
                  f"; tested {c['tested_pct']}%, documented {c['described_pct']}%; depth {c['mean_depth']} (0 = reads only raw inputs).\n")
    ov.append("\n## Most depended-on objects\n\n")
    hubs = sorted((n for n in g["nodes"] if n["declared"]), key=lambda n: (-len(down[n["id"]]), n["name"]))[:10]
    for n in hubs:
        if down[n["id"]]:
            ov.append(f"- `{n['name']}` ({n['kind']}) is used directly by {len(down[n['id']])} objects.\n")
    ov.append(f"\n## Health\n\n- Issues found by `data_graph.py check`: {len(chk['issues'])} ({', '.join(f'{k}={v}' for k, v in sorted(collections.Counter(i['type'] for i in chk['issues']).items())) or 'none'}).\n")
    ov.append(f"- Objects without tests: {len(chk['untested'])}. Without description: {len(chk['undocumented'])}.\n")
    docs["overview.md"] = "".join(ov)

    byf: dict[str, list[dict]] = collections.defaultdict(list)
    for n in g["nodes"]:
        if n["kind"] not in ("missing",) and n["declared"]:
            byf[n["folder"] or "(root)"].append(n)
    for f, ns in sorted(byf.items()):
        parts, cur, size = [], [], 0
        for n in sorted(ns, key=lambda x: x["name"]):
            card = _card(n, nodes, up, down)
            if cur and size + len(card) > CARD_CAP:
                parts.append(cur); cur, size = [], 0
            cur.append(card); size += len(card)
        if cur:
            parts.append(cur)
        for i, cards in enumerate(parts, 1):
            suffix = f"-{i}" if len(parts) > 1 else ""
            title = f"Data graph: {f}" + (f" (part {i}/{len(parts)})" if len(parts) > 1 else "")
            docs[f"cards-{slug(f)}{suffix}.md"] = fm(f"data-graph-{slug(f)}{suffix}", title, sorted({c_ for c_ in [n['path'] for n in ns if n['path']]})[:3]) + "".join(cards)
    return docs


def _card(n: dict, nodes, up, down) -> str:
    u = sorted(nodes[x]["name"] for x in up[n["id"]])
    d = sorted(nodes[x]["name"] for x in down[n["id"]])
    what = n["kind"] if not n["materialization"] or n["materialization"] == n["kind"] else f"{n['materialization']} {n['kind']}"
    lines = [f"## {n['name']}\n\n", f"{n['name']} is a {what}"]
    where = f" in `{n['path']}`" if n["path"] else ""
    sch = f", target {'.'.join(x for x in (n['database'], n['schema']) if x)}" if (n["schema"] or n["database"]) else ""
    lines.append(f"{where}{sch}.\n")
    if n["description"]:
        lines.append(f"{n['description']}\n")
    lines.append(f"{n['name']} depends on: {', '.join(u) if u else 'nothing (raw input)'}.\n")
    lines.append(f"{n['name']} is used by: {', '.join(d) if d else 'nothing in this repo'}.\n")
    if n["columns"]:
        cs = ", ".join(c["name"] for c in n["columns"][:25]) + (f" (+{len(n['columns']) - 25} more)" if len(n["columns"]) > 25 else "")
        lines.append(f"Columns: {cs}.\n")
    if n["tests"]:
        lines.append(f"Tests: {', '.join(n['tests'])}.\n")
    extra = []
    if n.get("partitioned_by"): extra.append("partitioned by " + ", ".join(n["partitioned_by"]))
    if n.get("clustered_by"): extra.append("clustered by " + ", ".join(n["clustered_by"]))
    if n.get("rows") is not None: extra.append(f"~{n['rows']} rows (last live scan)")
    if n.get("tags"): extra.append("tags: " + ", ".join(n["tags"]))
    if n.get("live") is True: extra.append("exists in the live system")
    if extra:
        lines.append("; ".join(extra).capitalize() + ".\n")
    return "".join(lines) + "\n"


RULES_STUB = """---
id: data-graph-rules
type: business-rule
status: draft
---
# Data project rules (human-written)

This file is yours: the generator never overwrites it. Promote a convention from `overview.md`
("Observed conventions") only after you confirm it is a real rule. Examples of what belongs here:
layer responsibilities, naming rules, who may read sources directly, SLA per mart, deprecated models.
"""


# ----------------------------------------------------------------------------- build
def build(repo: Path, tools: str = "auto", write_docs: bool = True) -> dict:
    g = Graph()
    scan_dbt(repo, g, use_manifest=(tools != "off" and True))
    scan_dataform(repo, g, tools)
    scan_databricks(repo, g)
    g.resolve()
    live_p = repo / ".agent-memory" / "data-sync-state" / "live.json"
    if live_p.exists():
        try:
            merge_live(g, json.loads(live_p.read_text()))
        except (OSError, ValueError):
            pass
    for n in g.nodes.values():
        shape(n)
    data = g.to_json()
    if write_docs:
        out = repo / OUT_REL
        out.mkdir(parents=True, exist_ok=True)
        new = render_docs(data)
        for f in out.glob("*.md"):
            if f.name != "rules.md" and f.name not in new:
                f.unlink()
        for name, text in new.items():
            if not (out / name).exists() or (out / name).read_text() != text:
                (out / name).write_text(text, encoding="utf-8")
        if not (out / "rules.md").exists():
            (out / "rules.md").write_text(RULES_STUB, encoding="utf-8")
        gj = json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
        if not (out / "graph.json").exists() or (out / "graph.json").read_text() != gj:
            (out / "graph.json").write_text(gj, encoding="utf-8")
    return data


def load_graph(repo: Path) -> dict:
    p = repo / OUT_REL / "graph.json"
    if not p.exists():
        sys.exit("no graph yet: run `data_graph.py build` first")
    return json.loads(p.read_text())


# ----------------------------------------------------------------------------- queries
def resolve_node(g: dict, q: str) -> dict:
    ql = q.lower()
    ids = [n for n in g["nodes"] if n["id"].lower() == ql]
    ids = ids or [n for n in g["nodes"] if n["name"].lower() == ql]
    ids = ids or [n for n in g["nodes"] if n["name"].lower().endswith("." + ql) or n["id"].lower().endswith(ql)]
    if len(ids) == 1:
        return ids[0]
    if not ids:
        sys.exit(f"no node matches '{q}'. Try: data_graph.py find {q}")
    sys.exit("ambiguous, use the id: " + ", ".join(n["id"] for n in ids[:12]))


def walk(g: dict, start: str, direction: str, depth: int):
    up, down = adjacency(g)
    adj = up if direction == "up" else down
    seen, layer, out = {start}, [start], {}
    for lvl in range(1, depth + 1):
        nxt = []
        for n in layer:
            for m in sorted(adj[n]):
                if m not in seen:
                    seen.add(m); nxt.append(m); out[m] = lvl
        layer = nxt
        if not layer:
            break
    return out


def short(n: dict) -> str:
    return f"{n['name']} [{n['kind']}{'/' + n['materialization'] if n['materialization'] and n['materialization'] != n['kind'] else ''}]" + (f" {n['path']}" if n["path"] else "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--tools", choices=("auto", "run", "off"), default="auto"); b.add_argument("--no-docs", action="store_true")
    sub.add_parser("status")
    for c in ("find", "show", "upstream", "downstream", "impact"):
        p = sub.add_parser(c); p.add_argument("name"); p.add_argument("--depth", type=int, default=99); p.add_argument("--json", action="store_true")
    pp = sub.add_parser("path"); pp.add_argument("src"); pp.add_argument("dst")
    ck = sub.add_parser("check"); ck.add_argument("--json", action="store_true")
    a = ap.parse_args()
    repo = a.repo.resolve()
    if a.cmd == "build":
        d = build(repo, a.tools, not a.no_docs)
        print(f"graph: {len(d['nodes'])} nodes, {len(d['edges'])} edges; systems={','.join(d['systems']) or 'none'}; "
              + ", ".join(f"{k}:{v.get('tier')}" for k, v in d["sources"].items() if isinstance(v, dict) and v.get("tier")))
        return 0
    if a.cmd == "status":
        gp = repo / OUT_REL / "graph.json"
        if not gp.exists():
            print("graph: not built"); return 1
        d = json.loads(gp.read_text())
        print(f"graph: {len(d['nodes'])} nodes, {len(d['edges'])} edges; systems={','.join(d['systems'])}")
        return 0
    g = load_graph(repo)
    nodes = {n["id"]: n for n in g["nodes"]}
    if a.cmd == "find":
        hits = [n for n in g["nodes"] if a.name.lower() in n["name"].lower() or a.name.lower() in n["path"].lower()]
        print(json.dumps([n["id"] for n in hits]) if a.json else "\n".join(f"{n['id']}  {short(n)}" for n in hits[:60]) or "no matches")
        return 0
    if a.cmd == "check":
        r = check(g)
        if a.json:
            print(json.dumps(r, indent=1)); return 0
        c = collections.Counter(i["type"] for i in r["issues"])
        print(f"issues: {dict(c) or 'none'}; untested={len(r['untested'])}; undocumented={len(r['undocumented'])}")
        for i in r["issues"][:40]:
            print(f"  [{i['type']}] {i.get('node', '')} {i['detail']} {i.get('path', '')}".rstrip())
        return 0
    if a.cmd == "path":
        s, t = resolve_node(g, a.src), resolve_node(g, a.dst)
        up, down = adjacency(g)
        for adj, label in ((up, "depends on"), (down, "is used by")):
            prev, q = {s["id"]: None}, collections.deque([s["id"]])
            while q:
                x = q.popleft()
                if x == t["id"]:
                    chain = []
                    while x:
                        chain.append(nodes[x]["name"]); x = prev[x]
                    print(" -> ".join(chain[::-1]) + f"   ({label})")
                    return 0
                for y in sorted(adj[x]):
                    if y not in prev:
                        prev[y] = x; q.append(y)
        print("no dependency path"); return 1
    n = resolve_node(g, a.name)
    if a.cmd == "show":
        up, down = adjacency(g)
        info = dict(n); info["depends_on"] = sorted(nodes[x]["name"] for x in up[n["id"]]); info["used_by"] = sorted(nodes[x]["name"] for x in down[n["id"]])
        if a.json:
            print(json.dumps(info, indent=1)); return 0
        print(short(n))
        for k in ("description", "schema", "database", "tags", "tests", "source", "live", "partitioned_by", "clustered_by", "dynamic"):
            if n.get(k) not in (None, "", [], False):
                print(f"  {k}: {n[k]}")
        print(f"  columns: {', '.join(c['name'] for c in n['columns'][:30])}" if n["columns"] else "  columns: (none recorded)")
        print(f"  depends on: {', '.join(info['depends_on']) or '-'}\n  used by: {', '.join(info['used_by']) or '-'}")
        return 0
    direction = "up" if a.cmd == "upstream" else "down"
    res = walk(g, n["id"], direction, a.depth)
    if a.json:
        print(json.dumps({nodes[k]["id"]: v for k, v in res.items()})); return 0
    if a.cmd == "impact":
        by = collections.defaultdict(list)
        for k, v in res.items():
            by[v].append(nodes[k])
        print(f"impact of changing {n['name']}: {len(res)} downstream objects")
        for lvl in sorted(by):
            print(f"  depth {lvl}: " + ", ".join(f"{x['name']} ({x['kind']})" for x in sorted(by[lvl], key=lambda z: z['name'])))
        exp = [nodes[k]["name"] for k in res if nodes[k]["kind"] == "exposure"]
        if exp:
            print("  exposures affected: " + ", ".join(sorted(exp)))
        return 0
    for k, v in sorted(res.items(), key=lambda kv: (kv[1], nodes[kv[0]]["name"])):
        print(f"{'  ' * (v - 1)}{v}. {short(nodes[k])}")
    if not res:
        print("none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
