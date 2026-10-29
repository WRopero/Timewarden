#!/usr/bin/env python3
"""Memoria de dependencias y seguridad: que versiones hay, cuando cambiaron y por que. Determinista, sin LLM.

  snapshot <repo>   lee lockfiles/Dockerfiles, compara con .agent-memory/dependencies.json y registra cambios
                    (motivo `security` si el ultimo commit del lockfile menciona CVE/seguridad/vulnerabilidad)
  note <repo> --pkg P [--eco poetry|npm|runtime] [--reason security|upgrade] [--cve ID] [--date D] [--to V] [--from V] [--note T]
                    anota a mano un cambio (p. ej. una correccion de seguridad anterior a este registro)
  report <repo>     (re)escribe docs/agent-memory/security/dependencias.md (se indexa en Cognee con sync)
Fuentes: poetry.lock, package-lock.json, requirements*.txt fijados con ==, ARG/FROM de Dockerfile (node/python).
"""
import json, re, subprocess, sys, time
from pathlib import Path

SKIP = {"node_modules", ".git", ".venv", "venv", "__pycache__", ".next", "dist", "build"}
SEC_RE = re.compile(r"CVE-\d{4}-\d+|GHSA-[\w-]+|seguridad|vulnerab|security|audit", re.I)


def find(repo, name_glob):
    out = []
    for p in sorted(repo.rglob(name_glob)):
        if not any(part in SKIP for part in p.relative_to(repo).parts) and p.is_file():
            out.append(p)
    return out


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def poetry_all(lock):
    pk = {}
    cur = {}
    for ln in lock.read_text(encoding="utf-8").splitlines():
        if ln.startswith("[[package]]"):
            cur = {}
        m = re.match(r'(name|version) = "(.*)"', ln)
        if m:
            cur[m.group(1)] = m.group(2)
            if len(cur) == 2:
                pk[norm(cur["name"])] = cur["version"]
    return pk


def poetry_direct(pyproject):
    names = set()
    sec = None
    for ln in pyproject.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\[(.+)\]", ln.strip())
        if m:
            sec = m.group(1); continue
        if sec and re.match(r"tool\.poetry(\.group\.[\w-]+)?\.dependencies$", sec):
            m = re.match(r'([A-Za-z0-9_.-]+)\s*=', ln)
            if m and m.group(1).lower() != "python":
                names.add(norm(m.group(1)))
    return names


def npm_all(lock):
    d = json.loads(lock.read_text(encoding="utf-8"))
    return {k.split("node_modules/")[-1]: v["version"] for k, v in d.get("packages", {}).items() if k.startswith("node_modules/") and "version" in v}


def npm_direct(pkg):
    d = json.loads(pkg.read_text(encoding="utf-8"))
    return set(d.get("dependencies", {})) | set(d.get("devDependencies", {}))


def collect(repo):
    """-> (all_pkgs {eco:name:ver}, direct {eco:name:ver}, runtimes {nombre: ver}, lockfiles [rel])"""
    allp, direct, rt, locks = {}, {}, {}, []
    for lock in find(repo, "poetry.lock"):
        locks.append(lock.relative_to(repo).as_posix())
        pk = poetry_all(lock); pj = lock.with_name("pyproject.toml")
        dn = poetry_direct(pj) if pj.exists() else set()
        for n, v in pk.items():
            allp[f"pypi:{n}"] = v
            if n in dn: direct[f"pypi:{n}"] = v
    for lock in find(repo, "package-lock.json"):
        locks.append(lock.relative_to(repo).as_posix())
        pk = npm_all(lock); pj = lock.with_name("package.json")
        dn = npm_direct(pj) if pj.exists() else set()
        for n, v in pk.items():
            allp[f"npm:{n}"] = v
            if n in dn: direct[f"npm:{n}"] = v
    for rq in find(repo, "requirements*.txt"):
        for ln in rq.read_text(encoding="utf-8").splitlines():
            m = re.match(r"([A-Za-z0-9_.-]+)==([\w.]+)", ln.strip())
            if m and f"pypi:{norm(m.group(1))}" not in allp:
                allp[f"pypi:{norm(m.group(1))}"] = m.group(2); direct[f"pypi:{norm(m.group(1))}"] = m.group(2)
                locks.append(rq.relative_to(repo).as_posix())
    for pk in find(repo, "packages.yml"):  # paquetes de dbt (hub o git): solo inventario, OSV no los cubre
        txt = pk.read_text(encoding="utf-8")
        for m in re.finditer(r"^\s*-?\s*(?:package|git):\s*['\"]?([^\s'\"]+)['\"]?\s*\n(?:.*\n)*?\s*(?:version|revision):\s*\[?['\"]?([^\]\n'\"]+)", txt, re.M):
            direct[f"dbt-pkg:{m.group(1).split('/')[-1].replace('.git', '')}"] = m.group(2).strip()
        locks.append(pk.relative_to(repo).as_posix())
    for df in find(repo, "Dockerfile*"):
        t = df.read_text(encoding="utf-8")
        m = re.search(r"ARG NODE_VERSION=([\w.]+)", t) or re.search(r"FROM node:([\w.]+)", t)
        if m: rt["node"] = m.group(1)
        m = re.search(r"FROM python:([\w.]+)", t)
        if m: rt["python"] = m.group(1)
    return allp, direct, rt, sorted(set(locks))


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()


def state_path(repo):
    return Path(repo) / ".agent-memory" / "dependencies.json"


def load(repo):
    try:
        return json.loads(state_path(repo).read_text(encoding="utf-8"))
    except Exception:
        return None


def save(repo, st):
    state_path(repo).write_text(json.dumps(st, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def reason_for(repo, locks):
    subj = " ".join(git(repo, "log", "-1", "--format=%s %b", "--", l) for l in locks[:4])
    cves = sorted(set(re.findall(r"CVE-\d{4}-\d+|GHSA-[\w-]+", subj)))
    return ("security" if SEC_RE.search(subj) else "upgrade"), cves, git(repo, "log", "-1", "--format=%h", "--", *locks[:4]) if locks else ""


def snapshot(repo):
    allp, direct, rt, locks = collect(repo)
    cur = {**direct, **{f"runtime:{k}": v for k, v in rt.items()}}
    st = load(repo)
    today = time.strftime("%Y-%m-%d")
    if st is None:
        save(repo, {"baseline": today, "direct": cur, "changes": []}); return 0
    prev = st.get("direct", {}); new = []
    why, cves, commit = reason_for(repo, locks)
    for k in sorted(set(prev) | set(cur)):
        if prev.get(k) != cur.get(k):
            new.append({"date": today, "pkg": k, "from": prev.get(k), "to": cur.get(k), "reason": why, "cves": cves, "commit": commit, "auto": True})
    if new:
        st["changes"] = (st.get("changes", []) + new)[-300:]; st["direct"] = cur; save(repo, st)
    return len(new)


def note(repo, a):
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    pkg = opt("--pkg") or sys.exit("falta --pkg")
    st = load(repo) or {"baseline": time.strftime("%Y-%m-%d"), "direct": {}, "changes": []}
    eco = opt("--eco", "pypi")
    st["changes"].append({"date": opt("--date", time.strftime("%Y-%m-%d")), "pkg": pkg if ":" in pkg else f"{eco}:{pkg}", "from": opt("--from"), "to": opt("--to"),
                          "reason": opt("--reason", "security"), "cves": [opt("--cve")] if opt("--cve") else [], "commit": opt("--commit", ""), "note": opt("--note", ""), "auto": False})
    save(repo, st); print("OK: anotado")


def audit_result(repo):
    from_proj = ""
    cfg = Path(repo) / ".agent-memory" / "project.yaml"
    m = re.search(r"^project_id:\s*(\S+)", cfg.read_text(encoding="utf-8"), re.M) if cfg.exists() else None
    pid = m.group(1) if m else Path(repo).name
    p = Path.home() / ".local/share/agents_memory_system/audit" / f"{pid}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")), p
    except Exception:
        return None, p


def report(repo):
    repo = Path(repo); st = load(repo)
    if st is None:
        snapshot(repo); st = load(repo)
    allp, direct, rt, locks = collect(repo)
    aud, _ = audit_result(repo)
    body = ["# Dependencias, versiones y seguridad", "",
            "Generado por `memory_deps.py report` (sin LLM) desde los lockfiles. No editar a mano: el registro vive en `.agent-memory/dependencies.json`.", ""]
    body += ["## Runtimes", ""] + ([f"- {k}: {v}" for k, v in sorted(rt.items())] or ["- (no detectados)"]) + [""]
    for eco, title in (("pypi", "Python (versiones resueltas en el lock)"), ("npm", "Node/npm (versiones resueltas en el lock)"), ("dbt-pkg", "Paquetes dbt (packages.yml)")):
        items = sorted((k.split(":", 1)[1], v) for k, v in direct.items() if k.startswith(eco + ":"))
        if items:
            body += [f"## {title}", ""] + ["; ".join(f"{n} {v}" for n, v in items), ""]
    body += ["## Historial de cambios de versiones (mas reciente primero)", ""]
    ch = sorted(st.get("changes", []), key=lambda c: c["date"], reverse=True)[:40]
    for c in ch:
        tag = {"security": "SEGURIDAD", "upgrade": "actualizacion"}.get(c["reason"], c["reason"])
        cv = f" {', '.join(c['cves'])}" if c.get("cves") else ""
        frm = f"{c['from']} -> " if c.get("from") else "nuevo -> " if not c.get("from") and c.get("to") else ""
        body.append(f"- {c['date']} [{tag}{cv}] {c['pkg']}: {frm}{c.get('to') or 'eliminado'}" + (f" (commit {c['commit']})" if c.get("commit") else "") + (f". {c['note']}" if c.get("note") else ""))
    if not ch: body.append("- (sin cambios registrados desde la linea base " + st.get("baseline", "?") + ")")
    body += ["", "## Vulnerabilidades abiertas (auditoria OSV)", ""]
    if not aud:
        body.append("- [ ] Ejecutar la primera auditoria: `python3 -I " + str(Path(__file__).parent / "memory_audit.py") + " run . --force`")
    elif aud.get("error") and not aud.get("vulns"):
        body.append(f"- Ultima auditoria con error ({aud.get('at', '?')[:10]}): {aud['error'][:120]}")
    else:
        v = aud.get("vulns", [])
        body.append(f"Auditoria del {aud['at'][:10]}: {aud['checked']} paquetes, {len(v)} vulnerabilidad(es) abierta(s).")
        body += [""] + [f"- [ ] {x['severity']} {x['pkg']} {x['version']} · {x['id']}{' (' + ', '.join(x['cves']) + ')' if x['cves'] else ''}"
                        f"{' · corregida en ' + x['fixed'] if x.get('fixed') else ''}{' · directa' if x['direct'] else ' · transitiva'} — {x['summary'][:100]}" for x in v[:30]]
    text = "\n".join(body) + "\n"
    dest = repo / "docs/agent-memory/security/dependencias.md"
    old = dest.read_text(encoding="utf-8") if dest.exists() else ""
    old_body = old.split("\n---\n", 1)[-1] if old.startswith("---") else ""
    if old_body.strip() == text.strip():
        return False
    pid = (re.search(r"^project_id:\s*(\S+)", (repo / ".agent-memory/project.yaml").read_text(encoding="utf-8"), re.M) or [None, repo.name])[1]
    created = (re.search(r"^created_at:\s*(\S+)", old, re.M) or [None, time.strftime("%Y-%m-%d")])[1]
    fm = ["---", "id: security-dependencies", f"project_id: {pid}", "type: security", "status: verified", f"created_at: {created}",
          f"updated_at: {time.strftime('%Y-%m-%d')}", f"source_commit: {git(repo, 'rev-parse', '--short', 'HEAD')}", "source_paths:"] + [f"  - {l}" for l in locks] + ["---", ""]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(fm) + text, encoding="utf-8")
    return True


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("snapshot", "note", "report"):
        sys.exit(__doc__)
    r = Path(a[1]).resolve()
    if not (r / ".agent-memory/project.yaml").exists():
        sys.exit(0)
    if a[0] == "snapshot":
        n = snapshot(r); print(f"{n} cambio(s) de version registrados"); report(r)
    elif a[0] == "note":
        note(r, a); report(r)
    else:
        print("reescrito" if report(r) else "sin cambios")
