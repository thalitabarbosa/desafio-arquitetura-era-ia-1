# 0006. Uma chave virtual por consumidor, com orçamento e limite de requisições no gateway

- Status: aceita
- Data: 2026-11-23
- Nível: solução

## Contexto

O teto corporativo é US$ 100/mês para o helpdesk (ADR 0001). Na v1 não havia limite algum: um relatório que morre na borda continua gastando tokens (Diagnóstico da v1, dor 1). O gateway só consegue recusar por orçamento se souber o preço dos modelos simulados; sem isso calcula custo zero.

## Opções consideradas

1. Uma chave só para tudo.
2. **Uma chave por consumidor**, com orçamento e limite próprios, declaradas em `gateway/keys.json` e criadas na subida.
3. Uma chave por feature: granularidade maior do que qualquer decisão atual pede.

## Decisão

Opção 2. Chaves (valores no `.env`, nunca no arquivo versionado):

| chave (alias) | variável | capacidades | orçamento | limite |
|---|---|---|---|---|
| `helpdesk-app` | `HELPDESK_GATEWAY_KEY` | as 4 capacidades e seus destinos de fallback | US$ 100 a cada 30 dias | 600 req/min |
| `governance-budget-demo` | `GOVERNANCE_BUDGET_KEY` | `helpdesk-classify` | US$ 0,0001 | — |
| `governance-rpm-demo` | `GOVERNANCE_RPM_KEY` | `helpdesk-classify` | — | 2 req/min |

As duas últimas existem para demonstrar a recusa (roteiro de governança do README) sem precisar gastar US$ 100. Os preços por token de cada destino estão declarados em `gateway/config.yaml` (`input_cost_per_token`/`output_cost_per_token`), copiados da tabela do provider simulado. A recusa acontece no gateway, antes de qualquer chamada ao provider. A aplicação traduz recusa do gateway (`429` ou orçamento) em `429` para quem chamou (`QuotaExceeded`).

## Consequências

- A conta de uma classificação é ~US$ 0,00014 (9 tokens × 2,5e-6 + 12 tokens × 1e-5), maior que o orçamento da chave de demonstração: a primeira passa, a segunda é recusada.
- O limite por minuto da chave da aplicação é generoso (600) para não atrapalhar o relatório (34 lotes, 4 em paralelo).
- Gasto e limites são do LiteLLM: a contagem de RPM é em memória por instância do gateway (uma só aqui).

## Evidência

Roteiro de governança do README: `/admin/calls` com 1 chamada depois da primeira requisição e continua com 1 depois da recusa por orçamento; com a chave de RPM, a 3ª requisição no mesmo minuto recebe `429` e também não chega ao provider.
