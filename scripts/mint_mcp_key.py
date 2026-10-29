#!/usr/bin/env python3
"""Crea una API key en Cognee y la guarda sin imprimirla.

Uso: mint_mcp_key.py [mcp|plugin]
  mcp     (por defecto) -> COGNEE_MCP_API_TOKEN en deploy/docker/.env (luego recrear agents_cognee_mcp)
  plugin               -> COGNEE_API_KEY en ~/.cognee/.env (modo 0600); reiniciar el worker del plugin
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from cognee_adapter import Cognee, ENV_FILE, load_env

target = sys.argv[1] if len(sys.argv) > 1 else "mcp"
if target not in ("mcp", "plugin"):
    sys.exit(__doc__)
if target == "mcp":
    if load_env().get("COGNEE_MCP_API_TOKEN"):
        sys.exit("COGNEE_MCP_API_TOKEN ya existe; borra la linea del .env para regenerarla")
    key = Cognee()._request("POST", "/api/v1/auth/api-keys", json_body={"name": "agents-mcp"})["key"]
    with ENV_FILE.open("a") as f:
        f.write(f"COGNEE_MCP_API_TOKEN={key}\n")
    print("OK: COGNEE_MCP_API_TOKEN guardada en", ENV_FILE, "-> scripts/dc.sh up -d --force-recreate agents_cognee_mcp")
else:
    p = Path.home() / ".cognee" / ".env"
    p.parent.mkdir(mode=0o700, exist_ok=True)
    key = Cognee()._request("POST", "/api/v1/auth/api-keys", json_body={"name": "agents-claude-plugin"})["key"]
    with p.open("a") as f:
        f.write(f'COGNEE_API_KEY="{key}"\n')
    os.chmod(p, 0o600)
    print("OK: COGNEE_API_KEY guardada en", p, "-> reinicia el worker: pkill -f _cloud_worker.py")
