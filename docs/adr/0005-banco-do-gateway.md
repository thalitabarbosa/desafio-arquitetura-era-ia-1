# 0005. Adicionar o serviço gateway-db (Postgres) para as chaves virtuais do gateway

- Status: aceita
- Data: 2026-11-23
- Nível: solução

## Contexto

O requisito 5 exige chaves do próprio gateway (a aplicação não usa chave de provider), pelo menos uma com orçamento e uma com limite de requisições, criadas sem passo manual. No LiteLLM, chaves virtuais, gasto por chave e orçamento só existem com banco de dados (Prisma + Postgres). Sem banco, só existe a master key, que não tem orçamento nem limite.

## Opções consideradas

1. Só a master key, compartilhada com a aplicação: não atende governança, e a aplicação passaria a ter a chave que administra o gateway.
2. **Postgres dedicado ao gateway** (`postgres:16-alpine`, serviço `gateway-db`).
3. Implementar orçamento e limite na aplicação: duplicaria o que o gateway já faz e espalharia governança de volta para cada serviço.

## Decisão

Opção 2. O `gateway-db` existe só para o gateway (nenhum outro serviço o usa), sem porta exposta e sem volume nomeado: o estado de chaves e gasto é recriado pelo `bootstrap_keys.py` a cada ambiente novo, o que é o desejado num ambiente de avaliação local. A senha vem de `GATEWAY_DB_PASSWORD` no `.env`.

## Consequências

- Mais um serviço para subir e vigiar; o gateway só fica saudável depois do banco (`depends_on: service_healthy`).
- Com `docker compose down`, o gasto acumulado das chaves é perdido (aceito localmente; em produção o banco teria volume e backup).

## Evidência

`docker compose ps` mostra `gateway-db` saudável; `docker compose logs gateway | grep bootstrap` mostra as três chaves criadas; o roteiro de governança do README só funciona porque o gasto da chave é persistido.
