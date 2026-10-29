#!/usr/bin/env python3
"""Creates an API key in Cognee and saves it without printing it.

Usage: mint_mcp_key.py [mcp|plugin]
  mcp     (default) -> COGNEE_MCP_API_TOKEN in deploy/docker/.env (then recreate agents_cognee_mcp)
  plugin            -> COGNEE_API_KEY in ~/.cognee/.env (mode 0600); restart the plugin worker
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
        sys.exit("COGNEE_MCP_API_TOKEN already exists; delete the line from .env to regenerate it")
    key = Cognee()._request("POST", "/api/v1/auth/api-keys", json_body={"name": "agents-mcp"})["key"]
    with ENV_FILE.open("a") as f:
        f.write(f"COGNEE_MCP_API_TOKEN={key}\n")
    print("OK: COGNEE_MCP_API_TOKEN saved to", ENV_FILE, "-> scripts/dc.sh up -d --force-recreate agents_cognee_mcp")
else:
    p = Path.home() / ".cognee" / ".env"
    p.parent.mkdir(mode=0o700, exist_ok=True)
    key = Cognee()._request("POST", "/api/v1/auth/api-keys", json_body={"name": "agents-claude-plugin"})["key"]
    with p.open("a") as f:
        f.write(f'COGNEE_API_KEY="{key}"\n')
    os.chmod(p, 0o600)
    print("OK: COGNEE_API_KEY saved to", p, "-> restart the worker: pkill -f _cloud_worker.py")
