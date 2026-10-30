#!/usr/bin/env python3
"""Incremental sync of docs/agent-memory/**.md to Cognee.

Usage:
  sync_markdown.py <repo> [--apply] [--status] [--no-verify] [--only PREFIX]... [--max-docs N] [--batch-size N] [--parallel N]

Without --apply it only shows the plan (new / changed / unchanged / deleted).
Registry states: pending -> submitted -> indexed | unverified | error.
A document only becomes `indexed` if a search returns its `doc_id=` marker.
--only PREFIX (repeatable) restricts the plan, the deletions and the apply to paths under that prefix or equal to it;
--batch-size N (default 8) documents per cognify, --parallel N (default 2) batches at once; a failed batch does not stop the others.
--max-docs N indexes at most N new/changed/retry documents in this run (the rest stay pending for the next run).
"""
from __future__ import annotations

import argparse
import fcntl
import fnmatch
import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
            cfg.setdefault(key, []).append(re.sub(r"\s+#.*$", "", line[2:]).strip().strip("'\""))   # inline comments
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


def openspec_label(rel: str) -> dict:
    """Only openspec/specs/** are current specs. Everything under openspec/changes/** (delta specs included)
    takes the label of its change: archived = verified history, active = draft proposal."""
    if rel.startswith("openspec/specs/"):
        return {"type": "openspec-spec", "status": "verified"}
    if rel.startswith("openspec/changes/archive/"):
        return {"type": "openspec-change-archived", "status": "verified"}
    return {"type": "openspec-change", "status": "draft"}


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
                meta = {**meta, **openspec_label(rel)}
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


SCOPE: list[str] = []


def in_scope(path: str) -> bool:
    return not SCOPE or any(path == s or path.startswith(s.rstrip("/") + "/") for s in SCOPE)


def label_changed(path: str, entry: dict, d: dict) -> bool:
    """The chunk header carries type/status but the content hash does not: relabel when they differ.
    Entries indexed before the registry recorded the label are only re-checked for OpenSpec delta specs
    (the files that v0.3.1 and earlier mislabeled as current `openspec-spec`)."""
    if "type" in entry:
        return (entry["type"], entry.get("doc_status")) != (d["type"], d["status"])
    return path.startswith("openspec/changes/") and "/specs/" in path


def plan(docs: dict, entries: dict) -> dict[str, list[str]]:
    out = {"new": [], "changed": [], "unchanged": [], "deleted": [], "skipped": [], "retry": []}
    for path, d in docs.items():
        if d["status"] == "archived":
            out["skipped"].append(path)
        elif path not in entries:
            out["new"].append(path)
        elif entries[path]["hash"] != d["hash"] or label_changed(path, entries[path], d):
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
    body = re.sub(r"^---\n.*?\n---\n", "", d["text"], count=1, flags=re.S)
    opening = " ".join(body.split())[:300]   # the document's own first words: matches its first chunk even without a header
    for query in (f"[project-memory] {tail}", f"[memoria-proyecto] {tail}", opening, f"{title} {d['doc_id']}"):   # 2nd = legacy marker (before v0.2.3)
        try:
            res = c.search(dataset, query, "CHUNKS", top_k=8)
        except CogneeError:
            continue
        if any(ch.get("document_id") == data_id for grp in res for ch in grp.get("search_result", [])):
            return True
    return False


POLL_SECONDS = 5
BATCH_TIMEOUT = 1800        # seconds one batch may wait for Cognee to finish processing it
DEFAULT_BATCH = 8           # documents per cognify
DEFAULT_PARALLEL = 2        # batches processed at the same time (Cognee accepts concurrent cognify on one dataset)


def wait_processed(c: Cognee, ds_id: str, data_ids: list[str]) -> None:
    """Block until Cognee reports these items processed. Uses the per-item list when it covers them, else the dataset-wide pending count."""
    own, t0 = set(data_ids), time.time()
    while True:
        st = c.processing_status(ds_id)
        mine = [i for i in st.get("items", []) if i.get("id") in own]
        if (len(mine) == len(own) and all(i.get("completed") for i in mine)) or (len(mine) != len(own) and st.get("pending", 1) == 0):
            return
        if time.time() - t0 > BATCH_TIMEOUT:
            raise CogneeError(f"timed out after {BATCH_TIMEOUT}s waiting for Cognee to process the batch")
        time.sleep(POLL_SECONDS)


def apply(repo: Path, cfg: dict, docs: dict, reg: dict, do_verify: bool, max_docs: int = 0,
          batch_size: int = DEFAULT_BATCH, parallel: int = DEFAULT_PARALLEL) -> None:
    pid, dataset = cfg["project_id"], cfg["memory_dataset"]
    entries = reg.setdefault(pid, {})
    p = plan({k: v for k, v in docs.items() if in_scope(k)}, {k: v for k, v in entries.items() if in_scope(k)})
    if max_docs:
        budget = max_docs
        for key in ("new", "changed", "retry"):
            p[key] = p[key][:budget]
            budget -= len(p[key])
    c = Cognee()
    c.ensure_dataset(dataset)
    ds_id = next(x["id"] for x in c.datasets() if x["name"] == dataset)
    getattr(c, "token", None)   # log in once, before the worker threads share the client
    lock = threading.Lock()

    def save() -> None:
        with lock:
            save_registry(reg)

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

    if do_verify:   # an earlier run may have been cut short while Cognee kept working: search before deleting and re-adding
        def reconcile(path: str) -> bool:
            e = entries[path]
            if e.get("data_id") and verify(c, dataset, docs[path], e["data_id"], pid):
                e.update(status="indexed", last_error="")
                print(f"  reconciled {path}")
                return True
            return False
        cand = [x for x in p["retry"] if entries[x].get("data_id")]
        if cand:
            with ThreadPoolExecutor(max_workers=max(1, parallel * 2)) as ex:
                done = set(x for x, ok in zip(cand, ex.map(reconcile, cand)) if ok)
            p["retry"] = [x for x in p["retry"] if x not in done]
            save()

    todo = p["new"] + p["changed"] + p["retry"]
    size = max(1, batch_size)
    batches = [todo[i:i + size] for i in range(0, len(todo), size)]

    def run_batch(num: int, batch: list[str]) -> None:
        submitted: list[str] = []
        for path in batch:
            d = docs[path]
            try:
                if path in p["changed"] or path in p["retry"]:
                    retire(path)   # a retry must delete the stale item first: re-adding identical content is a no-op in Cognee
                r = c.add_text(dataset, payload(pid, d))
                data_id = r["data_ingestion_info"][0]["data_id"]
                entries[path] = {"doc_id": d["doc_id"], "hash": d["hash"], "commit": d["commit"],
                                 "schema_version": SCHEMA_VERSION, "embedder": EMBEDDER,
                                 "type": d["type"], "doc_status": d["status"],
                                 "status": "submitted", "data_id": data_id, "last_error": "",
                                 "updated": time.strftime("%Y-%m-%dT%H:%M:%S")}
                submitted.append(path)
                print(f"  submitted {path}")
            except (CogneeError, KeyError, IndexError) as exc:
                entries[path] = {**entries.get(path, {}), "doc_id": d["doc_id"], "hash": d["hash"],
                                 "status": "error", "last_error": str(exc)[:300]}
                print(f"  ERROR     {path}: {exc}")
            save()
        if not submitted:
            return
        print(f"  batch {num}/{len(batches)}: cognify ({len(submitted)} documents)...")
        t = time.time()
        try:
            c.cognify(dataset, background=True)   # returns at once: no HTTP timeout, however long Cognee takes
            wait_processed(c, ds_id, [entries[x]["data_id"] for x in submitted])
        except CogneeError as exc:
            for path in submitted:
                entries[path].update(status="error", last_error=f"cognify: {str(exc)[:250]}")
            save()
            print(f"  batch {num}/{len(batches)}: FAILED ({exc}); its documents stay for the next run")
            return
        print(f"  batch {num}/{len(batches)}: cognify done in {time.time() - t:.0f}s")
        for path in submitted:
            ok = verify(c, dataset, docs[path], entries[path]["data_id"], pid) if do_verify else True
            entries[path]["status"] = "indexed" if ok else "unverified"
            print(f"  {'indexed  ' if ok else 'UNVERIFIED'} {path}")
        save()

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        futs = [ex.submit(run_batch, i + 1, b) for i, b in enumerate(batches)]
        for f in futs:
            try:
                f.result()
            except Exception as exc:   # one broken batch must not stop the rest
                print(f"  batch crashed: {exc}")
    save()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--only", action="append", default=[], metavar="PREFIX")
    ap.add_argument("--max-docs", type=int, default=0)
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH, help="documents per cognify batch")
    ap.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL, help="batches processed at the same time")
    a = ap.parse_args()
    SCOPE.extend(a.only)
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
        p = plan({k: v for k, v in docs.items() if in_scope(k)}, {k: v for k, v in entries.items() if in_scope(k)})
        print(f"project={cfg['project_id']}: " + ", ".join(f"{k}={len(v)}" for k, v in p.items()))
        if not a.apply:
            for k in ("new", "changed", "retry", "deleted"):
                for path in p[k]:
                    print(f"  [{k}] {path}")
            return 0
        apply(repo, cfg, docs, reg, not a.no_verify, a.max_docs, a.batch_size, a.parallel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
