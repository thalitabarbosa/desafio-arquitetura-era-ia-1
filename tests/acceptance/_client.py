"""Cliente HTTP (só biblioteca padrão) dos testes de aceite da main.

Fala com a borda (BASE_URL, padrão http://localhost:8000) e com os endpoints /admin do
provider-fake (PROVIDER_URL, padrão http://localhost:8090).
"""
import http.client
import json
import os
import time
import urllib.parse

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
PROVIDER_URL = os.environ.get("PROVIDER_URL", "http://localhost:8090").rstrip("/")


def _conn(base: str, timeout: float) -> tuple[http.client.HTTPConnection, str]:
    url = urllib.parse.urlsplit(base)
    return http.client.HTTPConnection(url.hostname, url.port or 80, timeout=timeout), url.path


def call(method: str, base: str, path: str, payload=None, timeout: float = 120):
    """Faz a requisição sem seguir redirecionamentos. Devolve (status, headers, corpo, segundos)."""
    conn, prefix = _conn(base, timeout)
    body = None if payload is None else json.dumps(payload)
    start = time.monotonic()
    conn.request(method, prefix + path, body=body, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = resp.read()
    elapsed = time.monotonic() - start
    conn.close()
    return resp.status, resp.headers, data, elapsed  # headers sem diferenciar maiúsculas


def app_post(path: str, payload, timeout: float = 120):
    return call("POST", BASE_URL, path, payload, timeout)


def app_get(path: str, timeout: float = 30):
    return call("GET", BASE_URL, path, None, timeout)


def stream_post(path: str, payload, timeout: float = 120) -> dict:
    """POST que lê um text/event-stream à medida que chega e marca o tempo de cada evento."""
    conn, prefix = _conn(BASE_URL, timeout)
    start = time.monotonic()
    conn.request("POST", prefix + path, body=json.dumps(payload), headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    result = {"status": resp.status, "headers": resp.headers, "events": [], "first_chunk_s": None}
    if not result["headers"].get("Content-Type", "").startswith("text/event-stream"):
        result["body"] = resp.read()
        result["total_s"] = time.monotonic() - start
        conn.close()
        return result
    name, data = "message", None
    while True:
        line = resp.fp.readline()
        if not line:
            break
        line = line.decode("utf-8").rstrip("\r\n")
        if line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            data = json.loads(line[5:].strip())
        elif line == "" and data is not None:
            now = time.monotonic() - start
            if name == "message" and result["first_chunk_s"] is None:
                result["first_chunk_s"] = now
            result["events"].append((name, data, now))
            name, data = "message", None
    result["total_s"] = time.monotonic() - start
    conn.close()
    return result


def reset_provider() -> None:
    call("POST", PROVIDER_URL, "/admin/reset")


def fail(provider: str, mode: str, model: str | None = None) -> None:
    payload = {"provider": provider, "mode": mode}
    if model:
        payload["model"] = model
    status, _, body, _ = call("POST", PROVIDER_URL, "/admin/failures", payload)
    assert status == 200, body


def provider_calls(last: int = 500) -> list[dict]:
    """Chamadas recebidas pelo provider, da mais antiga para a mais recente."""
    _, _, body, _ = call("GET", PROVIDER_URL, f"/admin/calls?last={last}")
    return list(reversed(json.loads(body)))


def wait_report(status_url: str, limit_s: float) -> tuple[int, dict, dict, float]:
    """Consulta a URL de status até sair de pending/running. Devolve (status, corpo, headers, segundos)."""
    start = time.monotonic()
    while True:
        status, headers, body, _ = app_get(status_url)
        elapsed = time.monotonic() - start
        if status != 200 or json.loads(body)["state"] not in ("pending", "running"):
            return status, (json.loads(body) if body else {}), headers, elapsed
        if elapsed > limit_s:
            return status, json.loads(body), headers, elapsed
        time.sleep(1)


TICKET = {"ticket_id": "TK-00042", "text": "Meu pedido #481516 não chegou e já passou do prazo, urgente"}
EXTRACT_TICKET = {"ticket_id": "TK-00002", "text": "Tenho aqui a nota fiscal 530720. O produto veio quebrado "
                  "na caixa, pedido #605065. Sou cliente da loja há bastante tempo."}
