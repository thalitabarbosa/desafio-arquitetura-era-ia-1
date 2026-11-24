"""Healthcheck do serviço gateway: o LiteLLM responde e as chaves virtuais já foram criadas."""
import pathlib
import sys
import urllib.request

try:
    urllib.request.urlopen("http://127.0.0.1:4000/health/liveliness", timeout=3)
except Exception:
    sys.exit(1)
sys.exit(0 if pathlib.Path("/tmp/gateway-keys-ready").exists() else 1)
