# 0009. Ler a métrica de acoplamento e declarar schemas e errors como estáveis por natureza

- Status: aceita
- Data: 2026-11-23
- Nível: software

## Contexto

A régua é fixa (requisito 3): Ca, Ce, I = Ce/(Ce+Ca), A = classes abstratas (herdam de `typing.Protocol` ou `abc.ABC`) / classes, D = |A + I − 1|. Zona de dor: A < 0,5, I < 0,5 e D ≥ 0,5. Script: `metrics/coupling.py`; resultados em `metrics/results/`.

| versão | componentes na zona de dor |
|---|---|
| `v1-coupled` | `config` (D 1,00), `llm` (D 0,80), `schemas` (D 1,00) |
| `v2-decoupled` | `schemas`, `errors` (D 1,00) |
| `main` | `schemas`, `errors` (D 1,00) |

## Opções consideradas

1. Tirar `schemas` e `errors` da zona à força (um Protocol vazio ou um import artificial para mexer em A ou I): desenha o código pela fórmula.
2. **Declarar os dois como estáveis por natureza**, com justificativa.

## Decisão

Opção 2. Exceções declaradas:

- **`schemas`** (Ca 6, Ce 0): modelos pydantic de entrada e saída das rotas e do estado do relatório. São tipos de valor; mudam só quando o contrato da API muda, que é exatamente quando todos os dependentes *devem* mudar junto. Ser concreto e muito usado é o esperado.
- **`errors`** (Ca 7, Ce 0): as exceções de domínio. Não têm comportamento, só nome e mensagem; foram separadas de `ports` justamente para que o módulo de contratos fique puro (revisão 1 do plano).

Não são exceção, e estão fora da zona: o componente que chama o gateway (`adapters.gateway`: I 0,50, D 0,50) e as features (`classification` D 0,25, `extraction` D 0,25, `suggestion` D 0,33, `report` D 0,40).

Leitura dos números que não são exceção:

- `ports` (A 1,00, I 0,00, D 0,00): contrato estável e abstrato, sobre a Main Sequence. É o que o v1 não tinha.
- `main` (I 1,00, D 0,00): ponto de composição, instável por definição; depende de todos e ninguém depende dele.
- Os adaptadores ficam em I = 0,50, D = 0,50, na fronteira: concretos, importados só por `main` e dependentes só de `errors`.
- O D das features não caiu de 0,25 (v1) para perto de zero; ele mede distância da Main Sequence, e uma feature concreta que depende de pouco fica um pouco mais estável. O ganho está em *o que* elas importam: na v1, `config` e `llm`; na main, `ports`, `schemas` e `errors`.

## Consequências

- O critério de pronto da refatoração passa a ser: nenhum componente na zona de dor além destes dois.
- Se `schemas` ou `errors` ganharem comportamento (validação de negócio, lógica), deixam de ser estáveis por natureza e esta exceção precisa ser revista.

## Evidência

`python3 metrics/coupling.py app/helpdesk main` marca com `<- zona de dor` só `errors` e `schemas`; `metrics/results/{v1-coupled,v2-decoupled,main}.{csv,svg}`.
