# 0007. Timeout, retry e fallback no gateway; modelo fraco decidido feature por feature

- Status: aceita
- Data: 2026-11-23
- Nível: solução

## Contexto

Na v1 nenhuma chamada tinha timeout ou retry configurados: valiam os padrões dos SDKs, **600 s de timeout e 2 retries** tanto no `openai` quanto no `anthropic`. Contra os 30 s da borda, isso significa que um provider travado (`timeout` segura a conexão por 300 s) vira `504` na borda enquanto a aplicação continua esperando, e um provider em `error_500` vira 3 chamadas e um `500` para o usuário. Metade do helpdesk parava junto com um provider (Diagnóstico da v1, dor 3).

Os modelos `large` dos dois providers são equivalentes (mesma saída). Os `mini` são mais rápidos e baratos, e piores. Evidência coletada chamando cada tarefa nos dois tamanhos no provider simulado (saída determinística; lógica em `provider-fake/app/tasks.py`):

| tarefa | `large` | `mini` | diferença |
|---|---|---|---|
| classify `"Meu pedido #481516 não chegou e já passou do prazo, urgente"` | `{"category": "delivery", "priority": "high"}` | idêntica | nenhuma: a classificação não depende do tamanho |
| topics (lotes do mês) | temas e contagens | idênticos | nenhuma |
| suggest (mesmo ticket) | 2.412 caracteres: abertura + 5 passos + reforços + fechamento | 1.066 caracteres: mesma abertura e passos, menos reforços | mais curta, mesmo conteúdo essencial |
| extract TK-00002 `"...nota fiscal 530720 ... pedido #605065..."` | `{"order_number": "#605065", "product": null}` | `{"order_number": "#530720", "product": null}` | **pega o número da nota fiscal como pedido** |
| extract `"Quero devolver o pedido nº 112233, a air fryer não liga"` | `{"order_number": "#112233", "product": "air fryer"}` | `{"order_number": "#112233", "product": null}` | **não identifica o produto** |

## Opções consideradas

1. Mecanismos na aplicação (timeout, retry e fallback no adaptador): duplicaria o que o gateway faz e espalharia a política por serviço.
2. **Mecanismos no gateway**, com a aplicação cuidando só do prazo que cada feature aceita esperar.
3. Circuit breaker (cooldown de destino): fora do escopo, e torna a contagem de tentativas variável.

## Decisão

Opção 2.

**Onde mora cada mecanismo:**

| mecanismo | onde | valor |
|---|---|---|
| timeout por tentativa | gateway (`timeout`/`stream_timeout` em cada destino) | F1/F4: 3 s; F2: 5 s sem trecho; F3: 15 s por lote |
| retry | gateway (`router_settings.num_retries: 1`) | no máximo **2 tentativas por destino**, backoff exponencial do LiteLLM (0,5 s + jitter ≤ 0,75 s; em `429`, o `Retry-After`) |
| fallback técnico | gateway (`router_settings.fallbacks`) | o `large` equivalente no outro provider, para toda capacidade |
| fallback com modelo fraco | gateway, só onde decidido abaixo | `gpt-fake-mini` |
| prazo total de quem espera | aplicação (`adapters/gateway.py`, valores em `main.py`) | F1/F4: 12 s; F2: 14 s até o 1º trecho; F3: 50 s por lote |
| retries no SDK da aplicação | desligados (`max_retries=0`) | retries em camadas se multiplicam |
| cooldown | desligado (`disable_cooldowns: true`) | toda requisição faz a mesma sequência, que o `/admin/calls` confere |

Conta do pior caso da F1 com o primário em `timeout`: 3 s + backoff ≤ 1,25 s + 3 s + fallback ~1,1 s ≈ 8,4 s, dentro dos 12 s da aplicação e dos 15 s exigidos. Se também o fallback travar, a aplicação desiste em 12 s com `503`.

**Modelo fraco, feature por feature.** A pergunta não é "o gateway consegue?", é "uma resposta pior é melhor que nenhuma, para quem consome esta feature?".

### F1 Classificar — aceita o mini

O cliente está esperando a confirmação na abertura do ticket. A evidência mostra saída idêntica no mini; e uma prioridade errada seria corrigida por um atendente na fila. Sem `large`: `200` com a classificação do mini.

### F2 Sugerir resposta — aceita o mini

Há um humano no circuito: o atendente lê e edita antes de enviar. O mini entrega uma sugestão mais curta (1.066 contra 2.412 caracteres) com a mesma abertura e os mesmos passos; um rascunho menor é melhor que tela vazia. Sem `large`: `200` em streaming com o texto do mini.

### F3 Relatório de temas — aceita o mini

Painel interno, sem ação automática sobre o resultado, e a evidência mostra temas e contagens idênticos no mini. Sem `large`: a tarefa chega a `done` com o relatório do mini.

### F4 Extrair dados do pedido — falha explicitamente

Alimenta uma automação de troca **sem revisão humana**: um campo errado vira uma troca errada (frete, estoque, cliente). A evidência mostra o mini trocando o número do pedido pelo da nota fiscal e perdendo o produto. Uma resposta errada é pior que nenhuma. Sem `large`: `503` com `{"detail": ...}`, e o mini não é chamado; a automação deve deixar o ticket para tratamento manual.

## Consequências

- Com o primário de uma capacidade fora, a feature responde pelo outro provider; com os dois `large` fora, F1/F2/F3 degradam para o mini e F4 para.
- Custos de degradação são baixos (o mini é o mais barato), mas o README e este ADR precisam ser revistos se a qualidade do mini mudar.
- Sem circuit breaker, um provider fora continua recebendo 2 tentativas por requisição.

## Evidência

`tests/acceptance/test_resilience.py`: com `gpt-fake-large` em `error_500`, `/admin/calls` mostra até 2 chamadas `500` no primário e o sucesso em `claude-fake-large`; com os dois `large` em `error_500`, F1/F2/F3 terminam no `gpt-fake-mini` e F4 responde `503` sem chamada a mini; com o primário da F1 em `timeout`, resposta em ≤ 15 s.
