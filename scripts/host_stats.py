#!/usr/bin/env python3
"""Samples the Mac's load (CPU, memory, swap, disk, battery, processes) for Management Memory.

A container cannot see the Mac. This script (stdlib, read-only, 0 tokens) takes ONE sample and exits.
With no arguments it prints it as JSON. With --inetd, launchd launches it only when the dashboard presses «Measure the Mac now»
(127.0.0.1:8018, socket activation): there is no resident process and no periodic polling.
Install the trigger: host_stats_launchagent.sh install
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--inetd", action="store_true", help="serves one HTTP request over stdin/stdout (launched by launchd on demand)")
a = ap.parse_args()


def run(*cmd, timeout=8):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def cpu_pct():
    out = run("top", "-l", "2", "-n", "0", "-s", "1", timeout=15)
    m = re.findall(r"CPU usage:\s*([\d.]+)% user,\s*([\d.]+)% sys,\s*([\d.]+)% idle", out)
    if not m:
        return None
    u, s, i = map(float, m[-1])
    return {"user": u, "sys": s, "idle": i, "used": round(u + s, 1)}


def memory():
    total = int(run("sysctl", "-n", "hw.memsize").strip() or 0)
    vm = run("vm_stat")
    page = int(re.search(r"page size of (\d+)", vm).group(1)) if "page size" in vm else 16384
    g = lambda k: int((re.search(rf"{k}:\s+(\d+)", vm) or [0, 0])[1]) * page
    active, wired, comp, free, inactive, spec = g("Pages active"), g("Pages wired down"), g("Pages occupied by compressor"), g("Pages free"), g("Pages inactive"), g("Pages speculative")
    used = active + wired + comp
    sw = re.search(r"total = ([\d.]+)M\s+used = ([\d.]+)M", run("sysctl", "-n", "vm.swapusage"))
    press = re.search(r"free percentage:\s*(\d+)%", run("memory_pressure", "-Q"))
    return {"total": total, "used": used, "wired": wired, "compressed": comp, "available": free + inactive + spec,
            "swap_total": int(float(sw.group(1)) * 1048576) if sw else 0, "swap_used": int(float(sw.group(2)) * 1048576) if sw else 0,
            "free_pct": int(press.group(1)) if press else None}


def battery():
    out = run("pmset", "-g", "batt")
    m = re.search(r"(\d+)%;\s*([a-z ]+);", out)
    return {"pct": int(m.group(1)), "state": m.group(2).strip(), "on_ac": "AC Power" in out} if m else None


def top_procs():
    rows = run("ps", "-Ao", "pid=,pcpu=,rss=,comm=").splitlines()
    procs = []
    for r in rows:
        p = r.split(None, 3)
        if len(p) == 4:
            try:
                procs.append({"name": os.path.basename(p[3]), "cpu": float(p[1]), "rss": int(p[2]) * 1024})
            except ValueError:
                pass
    agg = {}
    for p in procs:  # groups by name (Chrome Helper, node...)
        e = agg.setdefault(p["name"], {"name": p["name"], "cpu": 0.0, "rss": 0, "n": 0})
        e["cpu"] += p["cpu"]; e["rss"] += p["rss"]; e["n"] += 1
    vals = list(agg.values())
    return {"by_cpu": sorted(vals, key=lambda x: -x["cpu"])[:6], "by_mem": sorted(vals, key=lambda x: -x["rss"])[:6]}


def sample():
    du = shutil.disk_usage("/System/Volumes/Data" if Path("/System/Volumes/Data").exists() else "/")
    boot = re.search(r"sec = (\d+)", run("sysctl", "-n", "kern.boottime"))
    return {"ts": time.time(), "cpu": cpu_pct(), "cpu_count": os.cpu_count(), "load": list(os.getloadavg()), "memory": memory(),
            "disk": {"total": du.total, "used": du.used, "free": du.free}, "battery": battery(),
            "uptime_s": int(time.time() - int(boot.group(1))) if boot else None, "procs": top_procs(),
            "model": run("sysctl", "-n", "hw.model").strip(), "os": run("sw_vers", "-productVersion").strip()}


ALLOWED_HOSTS = {"host.docker.internal:8018", "127.0.0.1:8018", "localhost:8018"}


def serve_inetd():
    """launchd (inetd-compatible) hands us ONE connection over stdin/stdout: respond with one measurement and exit. Zero usage while idle."""
    head = b""
    while b"\r\n\r\n" not in head and len(head) < 8192:
        chunk = sys.stdin.buffer.readline()
        if not chunk:
            break
        head += chunk
        if chunk in (b"\r\n", b"\n"):
            break
    lines = head.decode("latin-1").splitlines()
    host = next((l.split(":", 1)[1].strip().lower() for l in lines if l.lower().startswith("host:")), "")
    if host not in ALLOWED_HOSTS:  # anti DNS-rebinding: a browser cannot read this through a foreign domain
        body, code = b'{"error":"host not allowed"}', "421 Misdirected Request"
    elif not lines or not lines[0].startswith(("GET ", "POST ")):
        body, code = b'{"error":"invalid request"}', "400 Bad Request"
    else:
        body, code = json.dumps(sample()).encode(), "200 OK"
    sys.stdout.buffer.write(f"HTTP/1.1 {code}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n".encode() + body)
    sys.stdout.buffer.flush()


if a.inetd:
    serve_inetd()
else:
    print(json.dumps(sample(), indent=2))
