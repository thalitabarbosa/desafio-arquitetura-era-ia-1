# Plano de refatoração

> Versão 1 (antes do piloto). As revisões estão registradas no fim do documento, na ordem em que aconteceram.

## Ponto de partida: medição da `v1-coupled`

Medido com `python3 metrics/coupling.py <checkout da v1>/app/helpdesk v1-coupled` ([CSV](../metrics/results/v1-coupled.csv), [gráfico](../metrics/results/v1-coupled.svg)).

| componente | Ca | Ce | I | A | D | leitura |
|---|---|---|---|---|---|---|
| config | 6 | 0 | 0,00 | 0,00 | 1,00 | zona de dor: todo mundo lê chaves, URLs e nomes de modelo daqui |
| llm | 4 | 1 | 0,20 | 0,00 | 0,80 | zona de dor: os dois SDKs, concretos, importados por todas as features |
| schemas | 5 | 0 | 0,00 | 0,00 | 1,00 | zona de dor pela fórmula; são tipos de valor pydantic |
| tickets | 1 | 1 | 0,50 | 0,00 | 0,50 | leitura de arquivo, depende de `config` |
| classification, extraction, suggestion | 1 | 3 | 0,75 | 0,00 | 0,25 | features dependem de `config` + `llm` (concretos) |
| report | 1 | 4 | 0,80 | 0,00 | 0,20 | idem, mais `tickets` |
| main | 0 | 5 | 1,00 | 0,00 | 0,00 | rotas HTTP |

O problema não é o número em si: é *quem* está na zona de dor. `config` e `llm` são exatamente as partes voláteis (modelo, provider, credencial, formato de API) e são as mais importadas. Toda troca de modelo ou provider atravessa as features.

## Componentes-alvo e estratégia

| alvo | estratégia | resultado esperado |
|---|---|---|
| `llm` | **inverter a dependência**: as features passam a depender de um contrato `LanguageModel` (Protocol em `ports.py`); a implementação concreta vira `adapters/gateway.py`, que fala com o AI Gateway por nomes lógicos | `llm` deixa de existir; `ports` fica com A = 1 e I ≈ 0 (sobre a Main Sequence); o adaptador só é importado por `main` |
| `config` | **reduzir Ca**: nenhuma feature lê configuração; valores (nome lógico da capacidade, tamanho de lote) chegam pelo construtor, montados em `main` | Ca de `config` cai para 1; chaves e nomes físicos de modelo saem do `app/` e vão para o gateway |
| `tickets` | **inverter a dependência**: contrato `TicketRepository` em `ports.py`; implementação `adapters/ticket_file.py` | o relatório não sabe que os tickets vêm de um arquivo |
| features (`classification`, `suggestion`, `extraction`, `report`) | **compor em vez de acoplar a módulos globais**: cada feature vira uma classe que recebe o `LanguageModel` (e o `TicketRepository`) no construtor; `HTTPException` sai das features e vira erro de domínio, traduzido em `main` | features dependem só de abstrações e tipos de valor; I continua alto (≥ 0,5) e D cai |
| `schemas` | nenhuma: tipo de valor estável por natureza | declarar a exceção no ADR da métrica |
| `main` | vira o ponto de composição: monta adaptadores e features e mapeia erros de domínio para HTTP | único componente que importa os adaptadores |

## Critério de pronto (métrica + testes)

1. `python3 -m unittest discover -s tests/characterization -v` passa sem alteração na suíte (mesmo diff vazio contra `v1-coupled`).
2. Nenhum componente na zona de dor (A < 0,5, I < 0,5 e D ≥ 0,5), exceto os declarados estáveis por natureza no ADR da métrica (previsto: só `schemas`).
3. O componente que chama o gateway é o único que importa o SDK, e só `main` o importa.
4. `grep -rE "gpt-fake|claude-fake" app/` e `grep -rE "FAKE_OPENAI_KEY|FAKE_ANTHROPIC_KEY|sk-fake-openai|sk-ant-fake" app/` não retornam nada.

## Piloto

Componente do piloto: **`classification`** (a feature mais simples, saída curta e determinística, coberta por 5 casos da suíte). O piloto cria `ports.py`, `adapters/gateway.py` e o serviço `gateway` (LiteLLM) com a capacidade lógica `helpdesk-classify`; as outras features continuam no caminho antigo até a medição do piloto ser lida.

### Medição antes e depois do piloto

Antes = `v1-coupled`. Depois = commit do piloto (`Piloto: classificação pelo AI Gateway`), medido com o mesmo script sobre `app/helpdesk`.

| componente | antes (Ca, Ce, I, A, D) | depois (Ca, Ce, I, A, D) |
|---|---|---|
| classification | 1, 3, 0,75, 0,00, 0,25 | 1, 2, 0,67, 0,00, 0,33 |
| llm | 4, 1, 0,20, 0,00, 0,80 | 3, 1, 0,25, 0,00, 0,75 |
| config | 6, 0, 0,00, 0,00, 1,00 | 5, 0, 0,00, 0,00, 1,00 |
| ports (novo) | — | 3, 0, 0,00, 0,33, **0,67** (zona de dor) |
| adapters.gateway (novo) | — | 1, 1, 0,50, 0,00, 0,50 |
| main | 0, 5, 1,00, 0,00, 0,00 | 0, 7, 1,00, 0,00, 0,00 |

Suíte de caracterização: os 5 casos de classificação continuam com o mesmo corpo de resposta (o `large` atrás de `helpdesk-classify` é o mesmo `gpt-fake-large`).

O que a medição mostrou:

1. **`ports` nasceu na zona de dor.** O plano pôs os erros de domínio (`ModelUnavailable`, `InvalidModelOutput`) junto do contrato. Duas classes concretas e um Protocol dão A = 0,33; como `ports` é estável (I = 0), D = 0,67. A métrica apontou um problema real de desenho: o módulo de contratos estava misturando contrato com tipos concretos.
2. **O D da feature piorou um pouco (0,25 → 0,33), e está certo.** A classificação passou a depender de menos coisas (Ce 3 → 2), então ficou um pouco mais estável sem ficar mais abstrata. O ganho do piloto não aparece no D da feature, e sim em *quem* ela importa: antes, `config` e `llm` (voláteis e concretos); depois, `ports` (abstrato) e `schemas` (tipos de valor). O critério de pronto não vai exigir D baixo nas features; vai exigir que elas fiquem fora da zona de dor e dependam só de abstrações e tipos de valor.
3. **Reduzir o Ca de `config` não tira `config` da zona de dor.** Um módulo folha e concreto tem I = 0 e A = 0 com Ca = 6 ou com Ca = 1. Injetar valores pelas features só desloca o problema.

## Revisões do plano

### Revisão 1 (depois do piloto): erros de domínio fora de `ports`

- **Antes:** `ports.py` com os Protocols e as exceções de domínio.
- **Depois:** `ports.py` só com Protocols (A = 1, sobre a Main Sequence). As exceções vão para `errors.py`, um módulo de tipos de domínio que quase nunca muda, como `schemas.py`; os dois são declarados estáveis por natureza no ADR da métrica (0009).
- **Por quê:** item 1 da medição. Separar contrato de tipo concreto é melhor estrutura mesmo sem a métrica: os adaptadores precisam lançar os erros sem depender do contrato que implementam.

### Revisão 2 (depois do piloto): `config` deixa de existir

- **Antes:** reduzir o Ca de `config` injetando valores nas features.
- **Depois:** o que sobra de configuração da aplicação (URL e chave do gateway, nomes lógicos das capacidades, tamanho do lote, timeouts) é lido do ambiente no ponto de composição (`main.py`) e passado pelo construtor. Chaves dos providers, base URLs dos providers e nomes físicos de modelo saem da aplicação e vão para `gateway/config.yaml`.
- **Por quê:** item 3 da medição. Com o gateway, `config` perde quase todo o conteúdo; um módulo só para meia dúzia de variáveis de ambiente lidas uma vez na composição não paga a dependência.

### Critério de pronto revisado

1. Suíte de caracterização passa sem alteração.
2. Nenhum componente na zona de dor, exceto `schemas` e `errors` (declarados no ADR 0009). Features e `adapters.gateway` não podem ser exceção.
3. Features importam só `ports`, `schemas` e `errors`; `adapters.gateway` é o único componente que importa o SDK, e só `main` o importa.
4. `grep` de modelos físicos e chaves de provider em `app/` vazio; o serviço `app` não recebe `env_file: .env`.

## Execução da refatoração com agente (até a tag `v2-decoupled`)

### Handoff

- **Agente:** Claude (Anthropic), numa sessão do Claude Code com acesso ao repositório, ao script de métrica e à suíte.
- **O que foi entregue ao agente:** este plano (estratégias e critério de pronto), a medição da `v1-coupled`, a suíte `tests/characterization/` como contrato imutável e quatro regras explícitas:
  1. não alterar `tests/characterization/` (o `git diff v1-coupled -- tests/characterization` precisa ficar vazio);
  2. features importam só `ports`, `schemas` e `errors`; só `main` importa `adapters.*`;
  3. um modelo `large` por capacidade na `v2-decoupled` (um `mini` muda as saídas fixadas pela suíte);
  4. comportamento externo idêntico: mesmas rotas, respostas síncronas, mesmos status de erro (422 do período, 502 de saída fora do contrato).
- **Passos pedidos ao agente, um por vez, cada um seguido de medição:** piloto (`classification`), leitura da medição e revisão do plano, depois `extraction`, `suggestion`, `report` + `tickets` (vira `adapters/ticket_file.py`) e por fim remoção de `llm.py` e `config.py`.

### Como a métrica e os testes decidiram o que entrava

| proposta do agente | juiz | decisão |
|---|---|---|
| `ports.py` com Protocols e exceções juntos (piloto) | métrica: `ports` com A = 0,33, I = 0, D = 0,67 | **rejeitada** → revisão 1 (`errors.py` separado) |
| manter `config.py` com Ca reduzido | métrica: folha concreta continua com D = 1 | **rejeitada** → revisão 2 (configuração lida em `main.py`) |
| adaptadores herdando explicitamente dos Protocols | régua: herdar de um Protocol pode ser lido como "classe abstrata" e distorcer A do adaptador | **rejeitada**: conformidade estrutural (duck typing), sem herança |
| `report` em lotes paralelos já na `v2` | regra 4: muda o perfil de chamadas e o tempo de resposta; é decisão de execução (requisito 6) | **adiada** para a `main` (ADR 0004) |
| erros de domínio traduzidos em `main.py` com `add_exception_handler` | suíte: corpo `{"detail": "A data inicial é posterior à data final"}` e status 422/502 preservados | **aceita** |
| `grep` de modelos físicos e chaves em `app/` | critério 4 | **aceito** (saída vazia) |

O gate final antes da tag é a suíte inteira contra o compose (`python3 -m unittest discover -s tests/characterization -v`), com o gateway mapeando cada capacidade para o mesmo `large` da v1.

### Medição da `v2-decoupled`

[CSV](../metrics/results/v2-decoupled.csv), [gráfico](../metrics/results/v2-decoupled.svg).

| componente | Ca | Ce | I | A | D |
|---|---|---|---|---|---|
| adapters.gateway | 1 | 1 | 0,50 | 0,00 | 0,50 |
| adapters.ticket_file | 1 | 1 | 0,50 | 0,00 | 0,50 |
| classification | 1 | 3 | 0,75 | 0,00 | 0,25 |
| errors | 6 | 0 | 0,00 | 0,00 | 1,00 (estável por natureza, ADR 0009) |
| extraction | 1 | 3 | 0,75 | 0,00 | 0,25 |
| main | 0 | 8 | 1,00 | 0,00 | 0,00 |
| ports | 4 | 0 | 0,00 | 1,00 | 0,00 |
| report | 1 | 3 | 0,75 | 0,00 | 0,25 |
| schemas | 5 | 0 | 0,00 | 0,00 | 1,00 (estável por natureza, ADR 0009) |
| suggestion | 1 | 2 | 0,67 | 0,00 | 0,33 |

Critério de pronto: (2) só `schemas` e `errors` na zona de dor, ambos declarados; (3) features importam só `ports`, `schemas`, `errors`, e `adapters.gateway` (único com `import openai`) só é importado por `main`; (4) `grep` vazio e o serviço `app` sem `env_file`.
