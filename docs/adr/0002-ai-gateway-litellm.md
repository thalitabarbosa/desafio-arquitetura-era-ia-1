# 0002. Colocar o LiteLLM Proxy, self-hosted, entre a aplicação e os providers

- Status: aceita
- Data: 2026-11-23
- Nível: solução

## Contexto

Na v1 a aplicação depende do que é mais volátil: provider, nome do modelo, formato da API e credencial (`config.py` e `llm.py` na zona de dor, D = 1,00 e 0,80). Trocar um modelo exige deploy (dor 4). Requisitos do desafio: gateway self-hosted como serviço `gateway` no compose, nomes lógicos, chaves virtuais com orçamento e limite, timeout/retry/fallback, troca de modelo reiniciando só o gateway. Gateways SaaS estão fora porque o avaliador sobe tudo localmente.

## Opções consideradas

1. **LiteLLM Proxy** (`ghcr.io/berriai/litellm:v1.102.1`): API compatível com a da OpenAI, traduz para o formato Messages da Anthropic, tem chaves virtuais, orçamento, RPM, retries, fallbacks e preço por token configurável. Precisa de Postgres para as chaves.
2. Escrever um gateway próprio em FastAPI: controle total, mas é um produto a manter, e cada capacidade exigida vira código nosso.
3. Abstração só dentro da aplicação (biblioteca cliente multi-provider): resolve o formato, mas credenciais, orçamento e limites continuariam em cada serviço.

## Decisão

Opção 1, na posição de **proxy de saída da aplicação**: `app → gateway → provider-fake`. A borda (`edge`) continua na frente da aplicação; o gateway não é exposto pela borda, só na rede do compose (e na porta 4000 do host, para o roteiro de governança). A aplicação usa o SDK `openai` apontado para `http://gateway:4000/v1` com a chave virtual `HELPDESK_GATEWAY_KEY`.

A configuração é versionada em `gateway/` e montada no container (`./gateway:/gateway:ro`), por isso trocar modelo é editar o arquivo e reiniciar só o gateway. As chaves virtuais são criadas sem passo manual: `gateway/entrypoint.sh` sobe o LiteLLM e roda `gateway/bootstrap_keys.py`, que cria ou atualiza as chaves de `gateway/keys.json` usando a master key; o healthcheck só fica verde depois disso, e a aplicação depende dele (`condition: service_healthy`).

## Consequências

- Melhor: provider, modelo, credencial, preço, retry e fallback saem do `app/`; uma troca de modelo é config.
- Pior: mais uma peça no caminho (latência de alguns ms e um ponto de falha); precisa do Postgres (ADR 0005).
- Limitação encontrada e resolvida na aplicação: o gateway não conhece o prazo de quem chama. Os prazos por feature (12 s em F1/F4, 14 s até o primeiro trecho em F2, 50 s por lote em F3) moram em `app/helpdesk/main.py` e no adaptador (ADR 0004).
- Retries em mais de um lugar se multiplicam: o SDK da aplicação roda com `max_retries=0`; retry só no gateway.

## Evidência

`docker compose config` mostra o serviço `app` só com `GATEWAY_BASE_URL` e `GATEWAY_API_KEY`; `docker compose exec app env | grep -i fake` vazio; `/admin/calls` registra as chamadas com o modelo físico escolhido pelo gateway.
