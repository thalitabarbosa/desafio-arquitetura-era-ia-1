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
