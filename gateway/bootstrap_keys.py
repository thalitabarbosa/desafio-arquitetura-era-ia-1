"""Cria (ou atualiza) as chaves virtuais do gateway a partir de /gateway/keys.json.

Roda dentro do container do gateway, depois que o LiteLLM sobe. Idempotente: se a chave já
existe no banco, aplica /key/update com os mesmos limites; senão, /key/generate.
O valor de cada chave vem de uma variável de ambiente (key_env), nunca do arquivo versionado.
"""
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:4000"
MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]
SPEC = json.loads(pathlib.Path("/gateway/keys.json").read_text(encoding="utf-8"))
READY_MARKER = pathlib.Path("/tmp/gateway-keys-ready")


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method, headers={
        "Authorization": f"Bearer {MASTER_KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read() or b"{}")
        except ValueError:
            return err.code, {}
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return 0, {}


def wait_until_ready(deadline_s: float = 300) -> None:
    start = time.monotonic()
    while time.monotonic() - start < deadline_s:
        status, body = call("GET", "/health/readiness")
        # 200 basta: se o banco ainda estiver aquecendo, o upsert abaixo tenta de novo.
        if status == 200:
            return
        time.sleep(2)
    sys.exit("gateway não ficou pronto a tempo")


def upsert(entry: dict) -> None:
    entry = dict(entry)
    key = os.environ[entry.pop("key_env")]
    entry.pop("description", None)
    hashed = hashlib.sha256(key.encode()).hexdigest()
    for attempt in range(20):
        status, _ = call("GET", f"/key/info?key={hashed}")
        if status == 200:
            status, body = call("POST", "/key/update", {"key": key, **entry})
            action = "atualizada"
        else:
            status, body = call("POST", "/key/generate", {"key": key, **entry})
            action = "criada"
        if status == 200:
            print(f"[bootstrap] chave {entry.get('key_alias')} {action}", flush=True)
            return
        print(f"[bootstrap] tentativa {attempt + 1} falhou ({status}): {body}", flush=True)
        time.sleep(3)
    sys.exit(f"não foi possível criar a chave {entry.get('key_alias')}")


if __name__ == "__main__":
    wait_until_ready()
    for item in SPEC:
        upsert(item)
    READY_MARKER.write_text("ok")
    print("[bootstrap] chaves prontas", flush=True)
