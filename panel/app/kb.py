"""Project knowledge bases: size, re-ingestion cost, and candidates to compact or delete."""
from __future__ import annotations

import collections
import re
import statistics

from . import cognee_client as cognee
from . import config, observer, pg, storage, vectors

_AVG_TOKENS_PER_CALL_FALLBACK = 4000


def classify(name: str) -> tuple[str, str]:
    """(project, type) from the dataset name: <project>-knowledge | <project>_sessions | codebase-<repo>-<hash>.
    The project is normalized (underscore = hyphen) to group datasets with different separators."""
    norm = lambda x: x.replace("_", "-").lower()  # noqa: E731
    if name.endswith("-knowledge"):
        return norm(name[: -len("-knowledge")]), "knowledge"
    if name.endswith("_sessions") or name.endswith("-sessions"):
        return norm(name[: -len("_sessions")]), "sessions"
    m = re.match(r"codebase-(.+)-[0-9a-f]{6,}$", name)
    if m:
        return norm(m.group(1)), "code"
    return norm(name), "otro"


def _avg_tokens_per_call() -> int:
    t = observer.summary().get("total", {})
    return int(t.get("avg_tokens") or _AVG_TOKENS_PER_CALL_FALLBACK)


def _chunks_by_doc(schema: str) -> dict[str, dict]:
    try:
        with pg.connect() as con, con.cursor() as cur:
            cur.execute(f'select payload->>\'document_id\', count(*), coalesce(sum(length(payload->>\'text\')),0) '
                        f'from "{schema}"."DocumentChunk_text" group by 1')
            return {d: {"chunks": c, "chars": int(ch)} for d, c, ch in cur.fetchall()}
    except Exception:
        return {}


def dataset_report(ds: dict, graph_files: dict, summaries: dict, avg_tokens: int, registry_rows: list[dict]) -> dict:
    did, name = ds["id"], ds["name"]
    project, kind = classify(name)
    schema = pg.dataset_schema_name(did)
    docs = cognee.get(f"/api/v1/datasets/{did}/data") or []
    by_doc = _chunks_by_doc(schema)
    try:
        cols = vectors.collections(schema)
    except Exception:
        cols = []
    pg_bytes = sum(s["bytes"] for s in pg.schemas() if s["schema"] == schema)
    chunks = sum(v["chunks"] for v in by_doc.values())
    chars = sum(v["chars"] for v in by_doc.values())
    vec_rows = sum(c["rows"] or 0 for c in cols)
    vec_bytes = sum(c["bytes_total"] for c in cols)
    gf = graph_files.get(did, {})
    g = summaries.get(did, {})
    reg = {r["data_id"]: r for r in registry_rows if r.get("data_id")}
    est_calls = chunks * 2
    doc_rows = []
    for d in docs:
        c = by_doc.get(d["id"], {"chunks": 0, "chars": 0})
        r = reg.get(d["id"], {})
        doc_rows.append({"id": d["id"], "name": d.get("name"), "path": r.get("path"), "doc_id": r.get("doc_id"),
                         "status": r.get("status"), "bytes": d.get("dataSize"), "chunks": c["chunks"], "chars": c["chars"],
                         "est_tokens": int(c["chars"] / config.CHARS_PER_TOKEN),
                         "est_reingest_tokens": c["chunks"] * 2 * avg_tokens, "created": d.get("createdAt"),
                         "updated": r.get("updated")})
    flags = _flags(name, kind, doc_rows, reg, cols, registry_rows, project)
    footprint = pg_bytes + gf.get("bytes", 0) + gf.get("wal_bytes", 0) + sum(d["bytes"] or 0 for d in doc_rows)
    return {"id": did, "name": name, "project": project, "kind": kind, "schema": schema, "documents": len(docs),
            "raw_bytes": sum(d["bytes"] or 0 for d in doc_rows), "chunks": chunks, "chunk_chars": chars,
            "est_tokens": int(chars / config.CHARS_PER_TOKEN), "nodes": g.get("numNodes"), "edges": g.get("numEdges"),
            "vector_collections": len(cols), "vector_rows": vec_rows, "vector_bytes": vec_bytes, "pg_bytes": pg_bytes,
            "graph_bytes": gf.get("bytes", 0), "graph_wal_bytes": gf.get("wal_bytes", 0), "footprint_bytes": footprint,
            "est_reingest_calls": est_calls, "est_reingest_tokens": est_calls * avg_tokens, "avg_tokens_per_call": avg_tokens,
            "flags": flags, "docs": sorted(doc_rows, key=lambda x: -x["chunks"]), "collections": cols}


def _flags(name, kind, docs, reg, cols, registry_rows, project) -> list[dict]:
    out = []
    if not docs and kind != "sessions":
        out.append({"level": "info", "code": "empty", "text": "Dataset with no documents: candidate for deletion."})
    if kind == "code" and not docs:
        out.append({"level": "info", "code": "empty_code", "text": "Code dataset created by the plugin and empty (code indexing is turned off)."})
    if kind == "sessions":
        out.append({"level": "info", "code": "sessions", "text": f"Session history: {len(docs)} items. Each session close costs ~3 calls; check whether it's worth it."})
    mine = [r for r in registry_rows if r["project"] == project]
    bad = [r for r in mine if r["status"] != "indexed"]
    if bad and kind == "knowledge":
        out.append({"level": "warn", "code": "not_indexed", "text": f"{len(bad)} registry document(s) are not 'indexed' (retry with sync)."})
    ids = {d["id"] for d in docs}
    missing = [r for r in mine if r.get("data_id") and r["data_id"] not in ids]
    if missing and kind == "knowledge":
        out.append({"level": "warn", "code": "missing_in_cognee", "text": f"{len(missing)} registry document(s) do not exist in Cognee."})
    orphans = [d for d in docs if d["id"] not in reg]
    if orphans and kind == "knowledge":
        out.append({"level": "warn", "code": "orphans", "text": f"{len(orphans)} document(s) in Cognee with no registry entry (loaded by hand?)."})
    vb = sum(c["bytes_total"] for c in cols)
    edge = next((c for c in cols if c["table"] == "EdgeType_relationship_name"), None)
    if edge and vb and edge["bytes_total"] / vb > 0.4:
        out.append({"level": "tip", "code": "edges_dominate", "text": f"Relationship-type vectors account for {round(100 * edge['bytes_total'] / vb)}% of the vectors (each graph connection generates its own vector with a descriptive phrase): they are the first candidate if you need to compact."})
    chunk_counts = [d["chunks"] for d in docs if d["chunks"]]
    if len(chunk_counts) >= 4:
        med = statistics.median(chunk_counts)
        heavy = [d for d in docs if d["chunks"] > max(2 * med, 4)]
        if heavy:
            out.append({"level": "tip", "code": "heavy_docs", "text": f"{len(heavy)} document(s) with >2× the median chunk count (each chunk ≈ 2 Claude calls): " + ", ".join((d['path'] or d['name'] or '?').split('/')[-1] for d in heavy[:4])})
    if not any(c["has_ann_index"] for c in cols) and cols:
        out.append({"level": "info", "code": "no_ann", "text": "No ANN index (HNSW/IVFFlat): exact search; with small corpora that's the right choice, but it becomes slow at tens of thousands of rows."})
    return out


def overview() -> dict:
    datasets = cognee.get("/api/v1/datasets") or []
    gsum = cognee.get("/api/v1/datasets/graph-summary") or []
    summaries = {g["datasetId"]: g for g in gsum}
    gf = storage.graph_files()
    avg = _avg_tokens_per_call()
    reg = observer.registry()
    reports = [dataset_report(d, gf, summaries, avg, reg) for d in datasets]
    projects: dict = collections.OrderedDict()
    for r in reports:
        p = projects.setdefault(r["project"], {"project": r["project"], "datasets": [], "documents": 0, "chunks": 0,
                                               "footprint_bytes": 0, "est_reingest_tokens": 0, "vector_rows": 0})
        p["datasets"].append({"id": r["id"], "name": r["name"], "kind": r["kind"]})
        for k in ("documents", "chunks", "footprint_bytes", "est_reingest_tokens", "vector_rows"):
            p[k] += r[k] or 0
    for r in reports:  # the heavy detail is requested per dataset
        r.pop("docs"), r.pop("collections")
    return {"projects": list(projects.values()), "datasets": reports, "storage": storage.totals(), "avg_tokens_per_call": avg,
            "pg": pg.overview()}
