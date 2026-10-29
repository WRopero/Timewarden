#!/usr/bin/env python3
"""Auditoria de vulnerabilidades contra OSV (api.osv.dev) usando las versiones EXACTAS de los lockfiles. Sin LLM.

  run <repo> [--force] [--max-age-hours 24]   consulta OSV (si el ultimo resultado es viejo) y guarda el resultado
  status <repo> [--lang es|en]                resumen compacto para el briefing (no usa red)
Resultado en ~/.local/share/agents_memory_system/audit/<project_id>.json (fuera del repo). Si hay cambios, regenera
docs/agent-memory/security/dependencias.md (checklist de pendientes). Sin red: registra el error y no molesta.
Aceptar un riesgo: lista el ID en .agent-memory/security-ignore.txt (una linea: ID  motivo).
"""
import json, re, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import memory_deps as D  # noqa: E402

OSV = "https://api.osv.dev/v1"
ECO = {"pypi": "PyPI", "npm": "npm"}
SEV = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "MEDIUM": 2, "LOW": 1}


def post(path, body):
    req = urllib.request.Request(OSV + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=25))


def get(path):
    return json.load(urllib.request.urlopen(OSV + path, timeout=25))


def ignored(repo):
    p = Path(repo) / ".agent-memory/security-ignore.txt"
    return {ln.split()[0] for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")} if p.exists() else set()


def run(repo, force, max_age):
    allp, direct, rt, locks = D.collect(repo)
    old, path = D.audit_result(repo)
    if old and not force and not old.get("error"):
        age = (time.time() - datetime.fromisoformat(old["at"]).timestamp()) / 3600
        if age < max_age:
            return old, False
    res = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "checked": len(allp), "vulns": []}
    try:
        keys = sorted(allp)
        hits = {}
        for i in range(0, len(keys), 500):
            chunk = keys[i:i + 500]
            qs = [{"package": {"name": k.split(":", 1)[1], "ecosystem": ECO[k.split(":", 1)[0]]}, "version": allp[k]} for k in chunk]
            for k, r in zip(chunk, post("/querybatch", {"queries": qs}).get("results", [])):
                if r.get("vulns"):
                    hits[k] = [v["id"] for v in r["vulns"]]
        ign = ignored(repo); cache = {}
        for k, ids in hits.items():
            eco, name = k.split(":", 1)
            for vid in ids:
                if vid in ign:
                    continue
                if vid not in cache:
                    cache[vid] = get(f"/vulns/{vid}")
                v = cache[vid]
                if v.get("withdrawn"):
                    continue
                fixed = ""
                for af in v.get("affected", []):
                    if af.get("package", {}).get("name", "").lower().replace("_", "-") == name.lower():
                        for rg in af.get("ranges", []):
                            fx = [e["fixed"] for e in rg.get("events", []) if "fixed" in e]
                            if fx: fixed = fx[-1]
                sev = (v.get("database_specific", {}).get("severity") or "UNKNOWN").upper()
                cves = [x for x in v.get("aliases", []) if x.startswith("CVE-")]
                res["vulns"].append({"id": vid, "cves": cves, "pkg": name, "eco": eco, "version": allp[k], "severity": sev, "fixed": fixed,
                                     "direct": k in direct, "summary": (v.get("summary") or v.get("details", "")[:100]).replace("\n", " ")})
        res["vulns"].sort(key=lambda x: (-SEV.get(x["severity"], 0), not x["direct"], x["pkg"]))
    except Exception as exc:  # sin red u OSV caido: no es un fallo del proyecto
        res = {**(old or {"vulns": [], "checked": len(allp)}), "at": (old or {}).get("at", res["at"]), "error": f"{type(exc).__name__}: {exc}"[:200], "error_at": res["at"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    D.report(repo)
    return res, True


def status(repo, lang):
    es = lang == "es"
    aud, _ = D.audit_result(repo)
    if not aud:
        return [("Seguridad: auditoria de vulnerabilidades aun no ejecutada (se lanza sola al abrir sesion)." if es else "Security: vulnerability audit not run yet (starts on session open).")]
    age_d = (time.time() - datetime.fromisoformat(aud["at"]).timestamp()) / 86400
    v = aud.get("vulns", [])
    hi = sum(1 for x in v if SEV.get(x["severity"], 0) >= 3)
    head = (f"Seguridad: auditoria OSV de hace {age_d:.1f} d ({aud['checked']} paquetes): {len(v)} abierta(s), {hi} alta(s)/critica(s)" if es else
            f"Security: OSV audit {age_d:.1f} d ago ({aud['checked']} packages): {len(v)} open, {hi} high/critical")
    out = [head + (" [auditoria desactualizada]" if es and age_d > 7 else "")]
    if aud.get("error"):
        out[0] += f" · ultimo intento fallo: {aud['error'][:60]}"
    for x in v[:5]:
        out.append(f"  - [ ] {x['severity']} {x['pkg']} {x['version']} {x['id']}" + (f" -> {x['fixed']}" if x.get("fixed") else "") + (" (directa)" if x["direct"] else ""))
    if len(v) > 5:
        out.append(f"  - … +{len(v) - 5} (docs/agent-memory/security/dependencias.md)")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("run", "status"):
        sys.exit(__doc__)
    r = Path(a[1]).resolve()
    if not (r / ".agent-memory/project.yaml").exists():
        sys.exit(0)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if a[0] == "run":
        res, ran = run(r, "--force" in a, float(opt("--max-age-hours", 24)))
        print(("auditoria ejecutada: " if ran else "reciente, sin consultar: ") + f"{len(res.get('vulns', []))} abierta(s)" + (f" · error: {res['error']}" if res.get("error") else ""))
    else:
        print("\n".join(status(r, opt("--lang", "es"))))
