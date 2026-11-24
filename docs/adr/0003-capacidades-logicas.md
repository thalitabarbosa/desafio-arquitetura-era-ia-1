# 0003. Nomear capacidades por feature e mapear o modelo físico no gateway

- Status: aceita
- Data: 2026-11-23
- Nível: solução

## Contexto

Na v1 o nome do modelo físico está no código (`config.CLASSIFICATION_MODEL = "gpt-fake-large"` etc.). Cada feature tem requisitos de latência, custo e qualidade diferentes (ADRs 0004 e 0007), então o que a aplicação precisa pedir é "a capacidade de classificar", não "o gpt-fake-large".

## Opções consideradas

1. Um nome lógico por tamanho (`helpdesk-large`, `helpdesk-mini`): menos entradas, mas a aplicação volta a escolher o modelo, e não dá para trocar o modelo de uma feature sem mexer nas outras.
2. **Um nome lógico por feature**: `helpdesk-classify`, `helpdesk-suggest`, `helpdesk-topics`, `helpdesk-extract`.

## Decisão

Opção 2. Mapeamento em `gateway/config.yaml`:

| capacidade | feature | primário | fallback técnico | modelo fraco |
|---|---|---|---|---|
| `helpdesk-classify` | F1 | `gpt-fake-large` (openai) | `claude-fake-large` | `gpt-fake-mini` |
| `helpdesk-suggest` | F2 | `claude-fake-large` (anthropic) | `gpt-fake-large` | `gpt-fake-mini` |
| `helpdesk-topics` | F3 | `claude-fake-large` (anthropic) | `gpt-fake-large` | `gpt-fake-mini` |
| `helpdesk-extract` | F4 | `gpt-fake-large` (openai) | `claude-fake-large` | — |

Os primários são os mesmos da v1, para manter o comportamento. Os destinos de fallback são grupos internos (`<capacidade>-fallback`, `<capacidade>-weak`) encadeados em `router_settings.fallbacks`; a aplicação nunca os chama pelo nome. O modelo fraco é sempre o `gpt-fake-mini`, o mais barato (US$ 0,15/0,60 por milhão de tokens), já que nas tarefas em que o mini é aceito a saída dos dois minis serve igual.

Os nomes lógicos chegam às features pelo construtor, a partir de `main.py` (com override por variável de ambiente `CAPABILITY_*`).

## Consequências

- Trocar o modelo de uma feature não afeta as outras. Ver "Troca de modelo" no README.
- Cada capacidade carrega o próprio timeout e preço.
- Mais entradas no `model_list` (11), compensadas pelo comentário de cabeçalho do arquivo.

## Evidência

`grep -rE "gpt-fake|claude-fake" app/` vazio; trocar `model: openai/gpt-fake-large` por `openai/gpt-fake-mini` no bloco `helpdesk-classify` + `docker compose restart gateway` faz a próxima classificação aparecer em `/admin/calls` com `gpt-fake-mini`, sem reiniciar o `app`.
