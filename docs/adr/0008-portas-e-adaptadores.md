# 0008. Features dependem de contratos; um único adaptador fala com o gateway

- Status: aceita
- Data: 2026-11-23
- Nível: software

## Contexto

Na v1 cada feature importa `config` e `llm` (módulos concretos e voláteis) e lança `HTTPException`. A troca de provider ou de modelo atravessa as features, e testar uma feature sem o provider não é possível.

## Opções consideradas

1. Manter `llm.py` e só trocar o SDK para falar com o gateway.
2. **Portas e adaptadores**: features dependem de Protocols; implementações concretas em `adapters/`; montagem em `main.py`.
3. Injeção por framework (dependências do FastAPI) nas features: acoplaria as features ao framework web.

## Decisão

Opção 2:

- `ports.py`: só Protocols (`LanguageModel` com `complete`/`stream`, `TicketRepository`).
- `errors.py`: erros de domínio (`ModelUnavailable`, `QuotaExceeded`, `InvalidModelOutput`, `InvalidPeriod`, `TicketSourceUnavailable`).
- `adapters/gateway.py`: **o único componente que chama o gateway** (único `import openai` do `app/`); traduz falhas do gateway em erros de domínio e aplica o prazo de cada chamada.
- `adapters/ticket_file.py`: lê `data/tickets.jsonl`.
- Features (`classification`, `suggestion`, `extraction`, `report`) são classes que recebem o `LanguageModel`, o nome lógico e os prazos no construtor; importam só `ports`, `schemas` e `errors`.
- `jobs.py`: estado das tarefas assíncronas do relatório.
- `main.py`: ponto de composição (lê o ambiente, monta adaptadores e features), rotas e tradução de erros de domínio para HTTP. É o único componente que importa `adapters.*`.

Os adaptadores seguem os Protocols por tipagem estrutural, sem herdar deles.

## Consequências

- Trocar o gateway por outro (ou o SDK) muda um arquivo.
- As features podem ser testadas com um `LanguageModel` falso.
- Mais arquivos e uma indireção a mais para quem lê pela primeira vez.

## Evidência

`grep -rn "import openai\|from openai" app/` aponta só `app/helpdesk/adapters/gateway.py`; `grep -rn "adapters" app/helpdesk --include=*.py` aponta só `main.py` (e o próprio pacote); `metrics/results/main.csv`: `adapters.gateway` com Ca = 1.
