#!/usr/bin/env python3
"""Evalua la recuperacion: fuente esperada en el top-k, latencia, aislamiento.

Uso: memory_eval.py <cases.jsonl> --dataset NAME --project-id ID [--top-k 5]
Las preguntas sin respuesta (`unanswerable`) solo se reportan: abstenerse es una
decision del agente, no del recuperador.
"""
import argparse, json, statistics, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from cognee_adapter import Cognee
from sync_markdown import load_registry

ap = argparse.ArgumentParser()
ap.add_argument("cases", type=Path)
ap.add_argument("--dataset", required=True)
ap.add_argument("--project-id", required=True)
ap.add_argument("--top-k", type=int, default=5)
a = ap.parse_args()

reg = load_registry().get(a.project_id, {})
by_data = {e["data_id"]: e["doc_id"] for e in reg.values() if e.get("data_id")}
c = Cognee()
rows, lat = [], []
for line in a.cases.read_text().splitlines():
    case = json.loads(line)
    t = time.time()
    res = c.search(a.dataset, case["q"], "CHUNKS", top_k=a.top_k)
    dt = time.time() - t
    lat.append(dt)
    chunks = [ch for g in res for ch in g.get("search_result", [])]
    docs = []
    for ch in chunks:
        d = by_data.get(ch.get("document_id"), "?")
        if d not in docs:
            docs.append(d)
    hit = None if case.get("unanswerable") else bool(set(docs) & set(case["expect"]))
    rank = next((i + 1 for i, d in enumerate(docs) if d in case["expect"]), None)
    rows.append({**case, "docs": docs, "hit": hit, "rank": rank, "s": round(dt, 2)})
    mark = "n/a" if hit is None else ("OK " if hit else "FALLO")
    print(f"{case['id']} [{case['lang']}] {mark} rank={rank} {dt:.2f}s  {case['q'][:60]}")
    if hit is False:
        print(f"      esperado={case['expect']} obtenido={docs}")
ans = [r for r in rows if r["hit"] is not None]
ok = sum(1 for r in ans if r["hit"])
print(f"\nrecall@{a.top_k} (documento): {ok}/{len(ans)}  objetivo >= 17/20")
for lang in ("es", "en"):
    sub = [r for r in ans if r["lang"] == lang]
    print(f"  {lang}: {sum(r['hit'] for r in sub)}/{len(sub)}")
srt = sorted(lat)
print(f"latencia: p50={statistics.median(lat):.2f}s p95={srt[int(len(srt)*0.95)-1]:.2f}s max={max(lat):.2f}s")
Path(a.cases.with_suffix(".results.json")).write_text(json.dumps(rows, ensure_ascii=False, indent=1))
