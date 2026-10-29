#!/usr/bin/env python3
"""Incremental sync of docs/agent-memory/**.md to Cognee.

Usage:
  sync_markdown.py <repo> [--apply] [--status] [--no-verify]

Without --apply it only shows the plan (new / changed / unchanged / deleted).
Registry states: pending -> submitted -> indexed | unverified | error.
A document only becomes `indexed` if a search returns its `doc_id=` marker.
"""
from __future__ import annotations

import argparse
import fcntl
import fnmatch
import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cognee_adapter import Cognee, CogneeError  # noqa: E402

STATE_DIR = Path.home() / ".local" / "share" / "agents_memory_system"
REGISTRY = STATE_DIR / "registry.json"
LOCK = STATE_DIR / "sync.lock"
SCHEMA_VERSION = 1
EMBEDDER = "jinaai/jina-embeddings-v2-base-es"


# -- project configuration (minimal YAML, only the subset in use) -----
def load_project(repo: Path) -> dict:
    cfg: dict = {}
    key = sub = None
    for raw in (repo / ".agent-memory" / "project.yaml").read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if line.startswith("- "):
            cfg.setdefault(key, []).append(line[2:].strip().strip("'\""))
        elif ":" in line:
            k, v = [p.strip() for p in line.split(":", 1)]
            v = re.sub(r"\s+#.*$", "", v).strip("'\"")  # inline comments
            if indent == 0:
                key, sub = k, None
                cfg[k] = {} if v == "" else (int(v) if v.isdigit() else v)
                if v == "":
                    cfg[k] = []  # converted to a dict if it has subkeys
            else:
                if isinstance(cfg[key], list):
                    cfg[key] = {}
                cfg[key][k] = {"true": True, "false": False}.get(v, int(v) if v.isdigit() else v)
    return cfg


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def enumerate_docs(repo: Path, cfg: dict) -> dict[str, dict]:
    docs: dict[str, dict] = {}
    excludes = cfg.get("exclude", [])
    for pattern in cfg.get("sources", []):
        for path in sorted(repo.glob(pattern)):
            rel = path.relative_to(repo).as_posix()
            if not path.is_file() or any(fnmatch.fnmatch(rel, e) or fnmatch.fnmatch(path.name, e) for e in excludes):
                continue
            text = path.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(text)
            if rel.startswith("openspec/") and "type" not in meta:  # OpenSpec specs have no frontmatter
                meta = {**meta, "type": "openspec-spec" if "/specs/" in rel else "openspec-change-archived" if "/archive/" in rel else "openspec-change",
                        "status": "verified" if "/specs/" in rel or "/archive/" in rel else "draft"}
            docs[rel] = {
                "path": rel,
                "hash": hashlib.sha256(text.encode()).hexdigest(),
                "doc_id": meta.get("id", rel),
                "status": meta.get("status", "draft"),
                "type": meta.get("type", "doc"),
                "commit": meta.get("source_commit", ""),
                "updated_at": meta.get("updated_at", ""),
                "text": text,
            }
    return docs


def payload(project_id: str, d: dict) -> str:
    header = (f"[project-memory] project_id={project_id} doc_id={d['doc_id']} type={d['type']} "
              f"status={d['status']} path={d['path']} source_commit={d['commit']} updated_at={d['updated_at']}")
    return f"{header}\n{d['text']}"


# -- registry ------------------------------------------------------------------
def load_registry() -> dict:
    return json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {}


def save_registry(reg: dict) -> None:
    tmp = REGISTRY.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False))
    tmp.replace(REGISTRY)  # atomic write
    # Copy in a dedicated read-only directory (Management Memory mounts it; the rename
    # changes the inode, so a single-file bind-mount would become stale).
    view = STATE_DIR / "view"
    view.mkdir(exist_ok=True)
    (view / "registry.json.tmp").write_text(json.dumps(reg, indent=2, ensure_ascii=False))
    (view / "registry.json.tmp").replace(view / "registry.json")


def plan(docs: dict, entries: dict) -> dict[str, list[str]]:
    out = {"new": [], "changed": [], "unchanged": [], "deleted": [], "skipped": [], "retry": []}
    for path, d in docs.items():
        if d["status"] == "archived":
            out["skipped"].append(path)
        elif path not in entries:
            out["new"].append(path)
        elif entries[path]["hash"] != d["hash"]:
            out["changed"].append(path)
        elif entries[path]["status"] in ("error", "unverified", "pending", "submitted"):
            out["retry"].append(path)
        else:
            out["unchanged"].append(path)
    out["deleted"] = [p for p in entries if p not in docs or docs[p]["status"] == "archived"]
    out["deleted"] = [p for p in out["deleted"] if entries[p].get("data_id")]
    return out


def verify(c: Cognee, dataset: str, d: dict, data_id: str, project_id: str = "") -> bool:
    """A document is indexed if a search returns a chunk whose `document_id` is the data_id Cognee assigned to it.
    Two queries: the chunk header written by `payload()` (matches the first chunk of any document) and the title."""
    title = next((ln.lstrip("# ").strip() for ln in d["text"].splitlines() if ln.startswith("# ")), d["doc_id"])
    tail = f"project_id={project_id} doc_id={d['doc_id']} type={d['type']} status={d['status']}"
    for query in (f"[project-memory] {tail}", f"[memoria-proyecto] {tail}", f"{title} {d['doc_id']}"):   # 2nd = legacy marker (before v0.2.3)
        try:
            res = c.search(dataset, query, "CHUNKS", top_k=8)
        except CogneeError:
            continue
        if any(ch.get("document_id") == data_id for grp in res for ch in grp.get("search_result", [])):
            return True
    return False


def apply(repo: Path, cfg: dict, docs: dict, reg: dict, do_verify: bool) -> None:
    pid, dataset = cfg["project_id"], cfg["memory_dataset"]
    entries = reg.setdefault(pid, {})
    p = plan(docs, entries)
    c = Cognee()
    c.ensure_dataset(dataset)
    ds_id = next(x["id"] for x in c.datasets() if x["name"] == dataset)
    submitted: list[str] = []

    def retire(path: str) -> None:
        data_id = entries[path].get("data_id")
        if data_id:
            c._request("DELETE", f"/api/v1/datasets/{ds_id}/data/{data_id}")

    for path in p["deleted"]:
        try:
            retire(path)
            del entries[path]
            print(f"  deleted   {path}")
        except CogneeError as exc:
            entries[path].update(status="error", last_error=str(exc)[:300])
    for path in p["new"] + p["changed"] + p["retry"]:
        d = docs[path]
        try:
            if path in p["changed"] or path in p["retry"]:
                retire(path)   # a retry must delete the stale item first: re-adding identical content is a no-op in Cognee
            r = c.add_text(dataset, payload(pid, d))
            data_id = r["data_ingestion_info"][0]["data_id"]
            entries[path] = {"doc_id": d["doc_id"], "hash": d["hash"], "commit": d["commit"],
                             "schema_version": SCHEMA_VERSION, "embedder": EMBEDDER,
                             "status": "submitted", "data_id": data_id, "last_error": "",
                             "updated": time.strftime("%Y-%m-%dT%H:%M:%S")}
            submitted.append(path)
            print(f"  submitted {path}")
        except (CogneeError, KeyError, IndexError) as exc:
            entries[path] = {**entries.get(path, {}), "doc_id": d["doc_id"], "hash": d["hash"],
                             "status": "error", "last_error": str(exc)[:300]}
            print(f"  ERROR     {path}: {exc}")
        save_registry(reg)
    if submitted:
        print(f"  cognify ({len(submitted)} documents)...")
        t = time.time()
        try:
            c.cognify(dataset)
        except CogneeError as exc:
            for path in submitted:
                entries[path].update(status="error", last_error=f"cognify: {str(exc)[:250]}")
            save_registry(reg)
            raise
        print(f"  cognify done in {time.time() - t:.0f}s")
        for path in submitted:
            ok = verify(c, dataset, docs[path], entries[path]['data_id'], pid) if do_verify else True
            entries[path]["status"] = "indexed" if ok else "unverified"
            print(f"  {'indexed  ' if ok else 'UNVERIFIED'} {path}")
    save_registry(reg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    a = ap.parse_args()
    repo = a.repo.resolve()
    cfg = load_project(repo)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("another sync is in progress", file=sys.stderr)
            return 2
        reg = load_registry()
        docs = enumerate_docs(repo, cfg)
        entries = reg.get(cfg["project_id"], {})
        if a.status:
            counts: dict[str, int] = {}
            for e in entries.values():
                counts[e["status"]] = counts.get(e["status"], 0) + 1
            print(f"project={cfg['project_id']} dataset={cfg['memory_dataset']} registered={len(entries)} {counts}")
            return 0
        p = plan(docs, entries)
        print(f"project={cfg['project_id']}: " + ", ".join(f"{k}={len(v)}" for k, v in p.items()))
        if not a.apply:
            for k in ("new", "changed", "retry", "deleted"):
                for path in p[k]:
                    print(f"  [{k}] {path}")
            return 0
        apply(repo, cfg, docs, reg, not a.no_verify)
    return 0


if __name__ == "__main__":
    sys.exit(main())
