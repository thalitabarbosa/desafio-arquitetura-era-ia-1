# 0004. Modo de execução por feature: F1 e F4 síncronas, F2 em streaming, F3 assíncrona

- Status: aceita
- Data: 2026-11-23
- Nível: solução

## Contexto

Na v1 as quatro features respondem de forma síncrona atrás de uma borda que encerra com `504` qualquer requisição que passe 30 s sem enviar nenhum byte (`edge/nginx.conf`: `proxy_read_timeout 30s`). Tempos do provider simulado (latência até o 1º token + tokens ÷ velocidade):

| feature | saída | tempo com modelo large |
|---|---|---|
| F1 classificar | ~12 tokens | 0,8 + 12/40 ≈ 1,1 s |
| F2 sugerir | ~603 tokens (2.412 caracteres) | 0,8 + 603/40 ≈ 15,9 s; 1º token em 0,8 s |
| F3 relatório do mês | 34 lotes de ~360 tokens | ~9,9 s por lote; 34 em sequência ≈ 336 s |
| F4 extrair | ~15 tokens | ≈ 1,2 s |

Árvore de decisão aplicada a cada feature: **alguém está esperando agora?** → **cabe no orçamento de latência?** → **é consumível aos poucos?**

## Opções consideradas

Para cada feature: síncrono, streaming (SSE) ou Asynchronous Request-Reply (202 + URL de status).

## Decisão

### F1 Classificar ticket — síncrono

- *Alguém está esperando agora?* Sim: o cliente espera a confirmação na tela, na abertura do ticket.
- *Cabe no orçamento de latência?* Sim: ~1,1 s contra 3 s exigidos.
- *É consumível aos poucos?* Não: saída curta, de valores fixos; meio JSON não serve para nada.

Resposta `200` com o JSON completo. Prazo explícito de 12 s na aplicação (`SYNC_DEADLINE_S`), abaixo dos 15 s exigidos e dos 30 s da borda; esgotado, responde `503` com motivo.

### F2 Sugerir resposta — streaming (SSE)

- *Alguém está esperando agora?* Sim: o atendente olha a tela.
- *Cabe no orçamento de latência?* A resposta inteira, não (~16 s contra 1,5 s para ver algo). O primeiro token, sim (0,8 s).
- *É consumível aos poucos?* Sim: o atendente começa a ler e editar assim que o texto aparece.

`POST /tickets/reply-suggestion` responde `200 text/event-stream` com `data: {"chunk": ...}` por trecho e `event: end` no fim. Assíncrono resolveria os 30 s da borda, mas não a espera percebida: o atendente continuaria vendo nada até o fim. A aplicação espera o primeiro trecho antes de abrir o stream (prazo de 14 s, `STREAM_DEADLINE_S`): falha antes disso ainda vira status HTTP (`503`/`429`); falha depois vira `event: error` com `{"ticket_id", "message": "A geração foi interrompida"}`, porque o `200` já foi enviado. O header `X-Accel-Buffering: no` impede a borda (nginx, `proxy_buffering` ligado por padrão) de acumular o stream.

### F3 Relatório de temas — Asynchronous Request-Reply

- *Alguém está esperando agora?* Não: é um painel interno, e ninguém fica olhando.
- *Cabe no orçamento de latência?* Não: ~336 s em sequência (~85 s com 4 lotes em paralelo) contra 30 s da borda.
- *É consumível aos poucos?* Não: os temas só fecham quando todos os lotes forem contados; um relatório parcial engana.

Streaming manteria a conexão aberta por minutos só para não estourar a borda, por acidente. Callback não existe (o painel não expõe um). Por isso: `POST /reports/topics` responde `202` em milissegundos com `Location: /reports/topics/status/{id}` e `Retry-After: 5`; a URL de status responde `200` com `pending`/`running` (com `progress`, ex. `"1800/5000"`) ou `failed` (com `reason`), e `303 See Other` para `/reports/topics/{id}` quando a tarefa chega a `done`.

A tarefa roda no próprio processo da aplicação (`asyncio`), com estado em memória (`app/helpdesk/jobs.py`). Fila e worker separados dariam capacidade e sobreviveriam a reinícios, mas o volume é um relatório de vez em quando e sobreviver a reinício está fora do escopo; não valem um serviço a mais. Os lotes rodam 4 por vez (`REPORT_CONCURRENCY`), juntados na ordem dos lotes (o resultado é o mesmo da execução sequencial). Cada lote tem prazo de 50 s; o primeiro lote que falha leva a tarefa a `failed` e cancela os outros, então ela nunca fica presa em `running` e chega a `failed` em menos de 60 s.

### F4 Extrair dados do pedido — síncrono

- *Alguém está esperando agora?* Sim: a automação de troca espera o dado para seguir.
- *Cabe no orçamento de latência?* Sim: ~1,2 s.
- *É consumível aos poucos?* Não: um número de pedido parcial é pior que nenhum.

Igual à F1: `200` com JSON, prazo de 12 s, `503` explícito quando não há modelo confiável (ADR 0007).

## Consequências

- O contrato de F2 e F3 mudou depois da tag `v2-decoupled`; a suíte de caracterização da `main` foi atualizada (o texto e o relatório finais continuam os mesmos fixados na v1).
- F3 passa a ter estado: perde as tarefas se a aplicação reiniciar (aceito, fora do escopo) e não deduplica pedidos iguais (fora do escopo).
- Cancelar a geração no provider quando o cliente fecha o stream não é feito (fora do escopo).

## Evidência

`tests/acceptance/test_flows.py` mede pela borda: F1 ≤ 3 s; F2 primeiro trecho ≤ 1,5 s e antes da metade do total, com mais de 10 eventos (sem buffer no caminho); F3 `202` ≤ 1 s e relatório com `total_tickets = 5000` e 34 chamadas `topics` em `/admin/calls`. `tests/acceptance/test_resilience.py` cobre o `event: error` (`midstream_error`) e o `failed` da F3 em ≤ 60 s.
