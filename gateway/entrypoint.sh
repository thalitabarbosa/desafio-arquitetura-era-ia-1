#!/bin/sh
# Sobe o LiteLLM Proxy e, quando ele estiver pronto, cria/atualiza as chaves virtuais
# declaradas em /gateway/keys.json (sem passo manual). O healthcheck do serviço só
# fica verde depois disso.
set -e
rm -f /tmp/gateway-keys-ready
litellm --config /gateway/config.yaml --port 4000 &
LITELLM_PID=$!
python /gateway/bootstrap_keys.py
wait "$LITELLM_PID"
