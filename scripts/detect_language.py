#!/usr/bin/env python3
"""Detecta si un repositorio esta escrito en espanol o en ingles (heuristica de palabras funcionales, sin red).

Uso: detect_language.py <repo>
Salida (una linea, parseable): LANG=<es|en|unknown> CONFIDENCE=<0-1> SAMPLES=<n> ES=<n> EN=<n>
Muestrea README*, CLAUDE.md, AGENTS.md y docs/**/*.md (max 40 archivos, 20 KB cada uno).
Codigo de salida: 0 = confiable (>= 0.75), 2 = ambiguo o sin texto: PREGUNTA al usuario.
"""
import re, sys
from pathlib import Path

ES = set("el la los las de del que y en un una por para con no es se su al lo como mas pero sus le ya o este si porque esta entre cuando muy sin sobre tambien me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese eso ante ellos e esto mi antes algunos que unos yo otro otras otra el tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas algo nosotros".split())
EN = set("the of and to in is that for it as was with be by on not he this are or his from at which but have an had they you were their one all we can her has there been if more when will would who so no".split())
STOP_SHARED = {"a", "no", "e", "o", "me", "he", "an", "as", "if", "so", "be", "at", "or", "lo", "se"}
ES -= STOP_SHARED; EN -= STOP_SHARED

repo = Path(sys.argv[1]).resolve()
files = [p for pat in ("README*", "CLAUDE.md", "AGENTS.md") for p in repo.glob(pat)]
files += sorted((repo / "docs").rglob("*.md"))[:40] if (repo / "docs").exists() else []
es = en = n = 0
for f in files[:40]:
    try:
        txt = f.read_text(encoding="utf-8", errors="ignore")[:20000]
    except OSError:
        continue
    txt = re.sub(r"```.*?```|`[^`]*`|https?://\S+", " ", txt, flags=re.S)
    words = re.findall(r"[a-záéíóúñü]+", txt.lower())
    if len(words) < 30:
        continue
    n += 1
    es += sum(w in ES for w in words) + 3 * len(re.findall(r"[áéíóúñ¿¡]", txt.lower()))
    en += sum(w in EN for w in words)
tot = es + en
if n == 0 or tot < 40:
    print(f"LANG=unknown CONFIDENCE=0 SAMPLES={n} ES={es} EN={en}"); sys.exit(2)
lang, conf = ("es", es / tot) if es >= en else ("en", en / tot)
print(f"LANG={lang} CONFIDENCE={conf:.2f} SAMPLES={n} ES={es} EN={en}")
sys.exit(0 if conf >= 0.75 else 2)
