#!/usr/bin/env bash
# Reproduz as dores 1 a 3 do Diagnóstico da v1 (README). Rodar num checkout da tag v1-coupled,
# com o ambiente no ar (cp .env.example .env && docker compose up -d --build --wait).
# A dor 4 (troca de modelo) está descrita no README, porque exige editar app/.
set -u
EDGE=http://localhost:8000
FAKE=http://localhost:8090
J='Content-Type: application/json'
TICKET='{"ticket_id": "TK-00042", "text": "Meu pedido #481516 não chegou e já passou do prazo, urgente"}'
calls() { curl -s "$FAKE/admin/calls?last=${1:-50}" | python3 -c '
import json, sys
for c in reversed(json.load(sys.stdin)):
    print(f"  {c[\"ts\"][11:23]} {c[\"provider\"]:9} {c[\"model\"]:17} {str(c[\"task\"]):8} stream={c[\"stream\"]!s:5} status={c[\"status\"]} dur_ms={c[\"duration_ms\"]}")'; }

echo "== Dor 1: relatório do mês"
curl -s -X POST $FAKE/admin/reset >/dev/null
curl -s -o /dev/null -w "  status=%{http_code} tempo=%{time_total}s\n" -X POST $EDGE/reports/topics -H "$J" \
  -d '{"start": "2026-08-01", "end": "2026-08-31"}'
echo "  chamadas até o 504:"; calls
echo "  aguardando 60 s para ver a aplicação continuar chamando o provider depois do 504..."
sleep 60; echo "  chamadas 60 s depois:"; calls | tail -8

echo "== Dor 2: sugestão de resposta (tela parada até o fim)"
curl -s -X POST $FAKE/admin/reset >/dev/null
curl -s -o /dev/null -w "  status=%{http_code} primeiro_byte=%{time_starttransfer}s total=%{time_total}s\n" \
  -X POST $EDGE/tickets/reply-suggestion -H "$J" -d "$TICKET"

echo "== Dor 3a: anthropic em error_500"
curl -s -X POST $FAKE/admin/reset >/dev/null
curl -s -X POST $FAKE/admin/failures -H "$J" -d '{"provider": "anthropic", "mode": "error_500"}' >/dev/null
for p in classification reply-suggestion extraction; do
  curl -s -o /dev/null -w "  /tickets/$p status=%{http_code} tempo=%{time_total}s\n" -X POST $EDGE/tickets/$p -H "$J" -d "$TICKET"
done
calls

echo "== Dor 3b: anthropic em timeout"
curl -s -X POST $FAKE/admin/reset >/dev/null
curl -s -X POST $FAKE/admin/failures -H "$J" -d '{"provider": "anthropic", "mode": "timeout"}' >/dev/null
curl -s -o /dev/null -w "  /tickets/reply-suggestion status=%{http_code} tempo=%{time_total}s\n" \
  -X POST $EDGE/tickets/reply-suggestion -H "$J" -d "$TICKET"
calls
curl -s -X POST $FAKE/admin/reset >/dev/null
