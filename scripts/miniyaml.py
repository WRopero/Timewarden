"""YAML loader for the data scripts: PyYAML when importable, otherwise a small subset parser (stdlib only).

Subset: block mappings and sequences, inline [a, b] / {k: v}, quoted and plain scalars, `>` / `|` block scalars, comments.
Jinja braces (`{{ ... }}`) are neutralized first so dbt property files parse in both modes.
"""
from __future__ import annotations

import os
import re

_J_OPEN, _J_CLOSE = "⟦", "⟧"


def load(text: str):
    text = text.replace("{{", _J_OPEN).replace("}}", _J_CLOSE).replace("{%", "⟨").replace("%}", "⟩")
    if not os.environ.get("TIMEWARDEN_NO_PYYAML"):
        try:
            import yaml  # type: ignore
            return yaml.safe_load(text)
        except ImportError:
            pass
        except Exception:
            return None
    try:
        return _parse(text)
    except Exception:
        return None


def _scalar(v: str):
    v = v.strip()
    if v == "" or v in ("~", "null", "Null", "NULL"):
        return None
    if v[0] in "\"'" and v[-1] == v[0] and len(v) >= 2:
        return v[1:-1]
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in _split_flow(v[1:-1])] if v[1:-1].strip() else []
    if v.startswith("{") and v.endswith("}"):
        out = {}
        for part in _split_flow(v[1:-1]):
            if ":" in part:
                k, val = part.split(":", 1)
                out[k.strip().strip("\"'")] = _scalar(val)
        return out
    return v


def _split_flow(s: str) -> list[str]:
    parts, depth, cur, quote = [], 0, "", ""
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch; cur += ch
        elif ch in "[{":
            depth += 1; cur += ch
        elif ch in "]}":
            depth -= 1; cur += ch
        elif ch == "," and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _strip_comment(line: str) -> str:
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _parse(text: str):
    raw = text.splitlines()
    lines: list[tuple[int, str]] = []
    i = 0
    n = len(raw)
    entries = []
    while i < n:
        ln = raw[i]
        if not ln.strip() or ln.lstrip().startswith("#") or ln.strip() in ("---", "..."):
            i += 1
            continue
        indent = len(ln) - len(ln.lstrip(" "))
        body = _strip_comment(ln.strip())
        m = re.match(r"^((?:- )*)(.*?)\s*(:\s*)?([>|][+-]?)$", body)
        if m and (m.group(3) or m.group(1)) and m.group(4) and (body.endswith(">") or body.endswith("|") or body[-2:] in (">-", "|-", ">+", "|+")):
            head = body[: -len(m.group(4))].rstrip()
            block, j = [], i + 1
            while j < n and (not raw[j].strip() or len(raw[j]) - len(raw[j].lstrip(" ")) > indent):
                block.append(raw[j].strip()); j += 1
            joiner = "\n" if m.group(4).startswith("|") else " "
            entries.append((indent, head + ' "' + joiner.join(b for b in block if b).replace('"', "'") + '"'))
            i = j
            continue
        entries.append((indent, body))
        i += 1
    lines = entries
    pos = 0

    def block(indent: int):
        nonlocal pos
        if pos >= len(lines):
            return None
        if lines[pos][1].startswith("- ") or lines[pos][1] == "-":
            out = []
            while pos < len(lines) and lines[pos][0] == indent and (lines[pos][1].startswith("- ") or lines[pos][1] == "-"):
                ind, body = lines[pos]
                rest = body[1:].strip()
                if not rest:
                    pos += 1
                    out.append(block(lines[pos][0]) if pos < len(lines) and lines[pos][0] > indent else None)
                elif re.match(r"^[^\"'\[{][^:]*:(\s|$)", rest) or re.match(r"^[\"'][^\"']*[\"']\s*:(\s|$)", rest):
                    lines[pos] = (indent + 2, rest)
                    out.append(block(indent + 2))
                else:
                    pos += 1
                    out.append(_scalar(rest))
            return out
        out = {}
        while pos < len(lines) and lines[pos][0] == indent and not lines[pos][1].startswith("- "):
            ind, body = lines[pos]
            m = re.match(r"^([\"']?)(.+?)\1\s*:(?:\s+(.*))?$", body)
            if not m:
                pos += 1
                continue
            key, val = m.group(2), m.group(3)
            pos += 1
            if val is None or val == "":
                if pos < len(lines) and (lines[pos][0] > indent or (lines[pos][0] == indent and lines[pos][1].startswith("- "))):
                    out[key] = block(lines[pos][0])
                else:
                    out[key] = None
            else:
                out[key] = _scalar(val)
        return out

    return block(lines[0][0]) if lines else None
