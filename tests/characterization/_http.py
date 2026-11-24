"""Cliente HTTP mínimo (só biblioteca padrão) usado pela suíte de caracterização.

A suíte fala com a aplicação pela borda (BASE_URL, padrão http://localhost:8000) e usa os
endpoints /admin do provider-fake (PROVIDER_URL, padrão http://localhost:8090) para garantir
que ele está no modo normal e para conferir as chamadas recebidas.
"""
import json
import os
import pathlib
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
PROVIDER_URL = os.environ.get("PROVIDER_URL", "http://localhost:8090").rstrip("/")
FIXTURES = json.loads((pathlib.Path(__file__).parent / "fixtures.json").read_text(encoding="utf-8"))


class Response:
    def __init__(self, status: int, headers, body: bytes):
        self.status = status
        self.headers = headers
        self.body = body

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def request(method: str, url: str, payload=None, timeout: float = 60) -> Response:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(resp.status, resp.headers, resp.read())
    except urllib.error.HTTPError as err:
        return Response(err.code, err.headers, err.read())


def post(path: str, payload, timeout: float = 60) -> Response:
    return request("POST", f"{BASE_URL}{path}", payload, timeout)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_no_redirect = urllib.request.build_opener(_NoRedirect)


def get(path: str, timeout: float = 30) -> Response:
    """GET sem seguir redirecionamentos (para ver o 303 da URL de status)."""
    try:
        with _no_redirect.open(f"{BASE_URL}{path}", timeout=timeout) as resp:
            return Response(resp.status, resp.headers, resp.read())
    except urllib.error.HTTPError as err:
        return Response(err.code, err.headers, err.read())


def sse_events(body: bytes) -> list[tuple[str, dict]]:
    """Converte um corpo text/event-stream em [(evento, dados)]; evento padrão = "message"."""
    events = []
    for block in body.decode("utf-8").split("\n\n"):
        if not block.strip():
            continue
        name, data = "message", None
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        events.append((name, data))
    return events


def reset_provider() -> None:
    request("POST", f"{PROVIDER_URL}/admin/reset")


def last_calls(n: int = 10) -> list[dict]:
    return request("GET", f"{PROVIDER_URL}/admin/calls?last={n}").json()
