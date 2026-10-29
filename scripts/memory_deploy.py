#!/usr/bin/env python3
"""Registro de despliegues por entorno + estado de ramas respecto a lo desplegado. Determinista, sin LLM.

El registro vive en <repo>/.agent-memory/deployments.json (se versiona con el contrato del proyecto).
  record <repo> <entorno> [--commit REF] [--date AAAA-MM-DD] [--note TXT]   anota que REF (por defecto HEAD) quedo desplegado
  status <repo> [--lang es|en] [--branch RAMA]                              imprime estado compacto (lo usan el briefing y el checkpoint)
Un despliegue SOLO se registra tras comprobarlo (salud OK); el script no puede saber por si solo que se desplego.
"""
import json, subprocess, sys, time
from pathlib import Path

T = {
    "es": dict(none="Despliegues: sin registro (tras desplegar: memory_deploy.py record <repo> <entorno>).", head="Despliegues",
               unknown="commit {c} no existe en este clon (verifica)", same="HEAD desplegado", behind="{n} commit(s) en {b} SIN desplegar",
               br_merged="rama {b}: ya integrada en {m}; {st}", br_open="rama {b}: {a} commit(s) propios sobre {m}, NO integrada; {st}",
               dep="desplegada en {e}", undep="sin desplegar en {e}"),
    "en": dict(none="Deployments: none recorded (after deploying: memory_deploy.py record <repo> <env>).", head="Deployments",
               unknown="commit {c} not in this clone (verify)", same="HEAD deployed", behind="{n} commit(s) on {b} NOT deployed",
               br_merged="branch {b}: merged into {m}; {st}", br_open="branch {b}: {a} own commit(s) over {m}, NOT merged; {st}",
               dep="deployed to {e}", undep="not deployed to {e}"),
}


def git(repo, *a):
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def load(repo):
    p = Path(repo) / ".agent-memory" / "deployments.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"environments": {}, "history": []}


def main_branch(repo):
    rc, out = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if rc == 0 and out:
        return out.split("/", 1)[1]
    for b in ("master", "main"):
        if git(repo, "rev-parse", "--verify", "-q", b)[0] == 0:
            return b
    return "master"


def is_ancestor(repo, a, b):
    return git(repo, "merge-base", "--is-ancestor", a, b)[0] == 0


def status(repo, lang="es", branch=None):
    t = T[lang]; data = load(repo); envs = data.get("environments", {})
    if not envs:
        return [t["none"]]
    cur = branch or git(repo, "branch", "--show-current")[1] or "HEAD"
    mb = main_branch(repo); out = [t["head"] + ":"]
    for env, d in envs.items():
        c = d["commit"]; line = f"- {env}: {c[:7]} ({d.get('at', '?')})" + (f" · {d['note'][:80]}" if d.get("note") else "")
        if git(repo, "cat-file", "-e", c + "^{commit}")[0] != 0:
            out.append(line + " · " + t["unknown"].format(c=c[:7])); continue
        ahead = int(git(repo, "rev-list", "--count", f"{c}..{mb}")[1] or 0)
        if is_ancestor(repo, mb, c):
            out.append(line + " · " + t["same"].replace("HEAD", mb))
        else:
            subj = git(repo, "log", "--first-parent", "--format=%h %s", "-3", f"{c}..{mb}")[1].splitlines()
            out.append(line + " · " + t["behind"].format(n=ahead, b=mb))
            out += [f"    · {s[:110]}" for s in subj]
        if cur not in (mb, "HEAD"):
            deployed = is_ancestor(repo, cur, c)
            st = t["dep"].format(e=env) if deployed else t["undep"].format(e=env)
            if is_ancestor(repo, cur, mb):
                out.append("  " + t["br_merged"].format(b=cur, m=mb, st=st))
            else:
                n = git(repo, "rev-list", "--count", f"{mb}..{cur}")[1] or "?"
                out.append("  " + t["br_open"].format(b=cur, a=n, m=mb, st=st))
    return out


def record(repo, env, commit, date, note):
    rc, full = git(repo, "rev-parse", "--verify", commit + "^{commit}")
    if rc != 0:
        sys.exit(f"commit desconocido: {commit}")
    data = load(repo)
    entry = {"commit": full, "at": date or time.strftime("%Y-%m-%d"), "branch": git(repo, "branch", "--show-current")[1] or None}
    if note:
        entry["note"] = note
    data.setdefault("environments", {})[env] = entry
    data.setdefault("history", []).append({"env": env, **entry}); data["history"] = data["history"][-30:]
    p = Path(repo) / ".agent-memory" / "deployments.json"
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK: {env} -> {full[:7]} ({entry['at']}) en {p}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("record", "status"):
        sys.exit(__doc__)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    repo = Path(a[1]).resolve()
    if a[0] == "status":
        print("\n".join(status(repo, opt("--lang", "es"), opt("--branch"))))
    else:
        if len(a) < 3:
            sys.exit(__doc__)
        record(repo, a[2], opt("--commit", "HEAD"), opt("--date"), opt("--note"))
