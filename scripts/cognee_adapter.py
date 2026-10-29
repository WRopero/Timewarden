#!/usr/bin/env python3
"""Cliente minimo (stdlib) de la API de Cognee 1.6.5 para este stack.

Encapsula login, datasets, add/cognify/search/forget. Cada operacion exige un
dataset explicito: no hay dataset por defecto, para no mezclar proyectos.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "deploy" / "docker" / ".env"
BASE_URL = os.environ.get("COGNEE_BASE_URL", "http://127.0.0.1:45874")


def load_env(path: Path = ENV_FILE) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


class CogneeError(RuntimeError):
    pass


class Cognee:
    def __init__(self, base_url: str = BASE_URL, email: str | None = None, password: str | None = None):
        env = load_env()
        self.base_url = base_url.rstrip("/")
        self.email = email or env.get("COGNEE_USER_EMAIL", "")
        self.password = password or env.get("COGNEE_USER_PASSWORD", "")
        self._token: str | None = None

    # -- transporte -----------------------------------------------------
    def _request(self, method: str, path: str, *, json_body=None, form=None, multipart=None,
                 auth: bool = True, timeout: float = 600):
        headers = {}
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif multipart is not None:
            boundary = uuid.uuid4().hex
            parts = []
            for name, value in multipart:
                parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n")
            parts.append(f"--{boundary}--\r\n")
            data = "".join(parts).encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            raise CogneeError(f"{method} {path} -> {exc.code}: {exc.read()[:400].decode(errors='replace')}") from exc
        return json.loads(body) if body else None

    @property
    def token(self) -> str:
        if not self._token:
            out = self._request("POST", "/api/v1/auth/login",
                                form={"username": self.email, "password": self.password}, auth=False)
            self._token = out["access_token"]
        return self._token

    # -- operaciones ----------------------------------------------------
    def health(self) -> dict:
        return self._request("GET", "/health", auth=False)

    def ensure_dataset(self, name: str) -> dict:
        return self._request("POST", "/api/v1/datasets", json_body={"name": name})

    def datasets(self) -> list[dict]:
        return self._request("GET", "/api/v1/datasets")

    def add_text(self, dataset: str, text: str) -> dict:
        return self._request("POST", "/api/v1/add",
                             multipart=[("datasetName", dataset), ("raw_data", text)])

    def cognify(self, dataset: str, background: bool = False) -> dict:
        return self._request("POST", "/api/v1/cognify",
                             json_body={"datasets": [dataset], "runInBackground": background})

    def search(self, dataset: str, query: str, search_type: str = "CHUNKS", top_k: int = 5) -> list:
        return self._request("POST", "/api/v1/search", json_body={
            "searchType": search_type, "datasets": [dataset], "query": query, "topK": top_k})

    def processing_status(self, dataset_id: str) -> dict:
        return self._request("GET", f"/api/v1/datasets/{dataset_id}/processing-status")

    def forget_dataset(self, dataset: str) -> dict:
        return self._request("POST", "/api/v1/forget", json_body={"dataset": dataset})


if __name__ == "__main__":
    import sys
    c = Cognee()
    print(json.dumps(c.health()))
    if len(sys.argv) > 1 and sys.argv[1] == "datasets":
        print(json.dumps(c.datasets(), indent=2))
