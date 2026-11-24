# 0001. Aceitar só providers acessados por um gateway próprio, com teto mensal de gasto

- Status: aceita
- Data: 2026-11-23
- Nível: corporativa

## Contexto

O helpdesk colocou IA em quatro pontos sem política: cada feature escolheu um provider "porque funcionou melhor no teste", as chaves ficaram na configuração da aplicação e ninguém sabia quanto se gastava. Na última instabilidade de um provider, metade do helpdesk parou (Diagnóstico da v1, dor 3). A empresa precisa decidir *quais* providers aceita e *quanto* aceita gastar, antes de qualquer decisão técnica.

Conta de gasto (preços do provider simulado, volume de agosto: 5.000 tickets):

| uso | custo unitário | custo no mês |
|---|---|---|
| F1 classificar (gpt large, ~46 tokens in, 12 out) | US$ 0,00024 | US$ 1,20 |
| F2 sugerir (claude large, ~46 in, ~603 out) | US$ 0,0092 | US$ 46 |
| F4 extrair (gpt large, ~46 in, ~15 out) | US$ 0,00027 | US$ 1,35 |
| F3 relatório do mês (34 lotes, ~6.600 in e ~360 out cada) | US$ 0,86 por relatório | ~US$ 26 com 30 relatórios |
| **total** | | **~US$ 75** |

## Opções consideradas

1. Cada time escolhe provider e contrata como quiser (situação atual).
2. Um único provider homologado.
3. Dois providers homologados (OpenAI e Anthropic), sempre acessados por um gateway da empresa, com teto mensal.

## Decisão

Opção 3. A empresa aceita OpenAI e Anthropic como providers de IA; nenhum serviço fala com eles diretamente nem guarda chave deles — o acesso é pelo AI Gateway (ADR 0002). O teto de gasto do helpdesk com IA é **US$ 100 por mês**: a conta acima mais ~30% de folga. Um provider só não atende: é o que derrubou metade do helpdesk.

## Consequências

- Credencial de provider vira assunto de um lugar só (o gateway); os times recebem chaves virtuais.
- O teto vira configuração (ADR 0006): a chave da aplicação tem `max_budget: 100` com `budget_duration: 30d`. Estourar o teto para o helpdesk; mudar o teto é decisão desta instância, não do time.
- Entrar um terceiro provider exige revisar este ADR.

## Evidência

`gateway/keys.json` (chave `helpdesk-app`: `max_budget` e `budget_duration`); `grep -rE "FAKE_OPENAI_KEY|FAKE_ANTHROPIC_KEY" app/` vazio; `gateway/config.yaml` só tem destinos `openai/*` e `anthropic/*`.
