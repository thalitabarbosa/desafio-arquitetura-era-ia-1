"""Contratos de que as features dependem. Só Protocols: nenhuma implementação mora aqui."""
from collections.abc import AsyncIterator
from datetime import date
from typing import Protocol


class LanguageModel(Protocol):
    """Uma capacidade de linguagem pedida por nome lógico; quem escolhe o modelo físico é o gateway.

    `deadline` é o tempo máximo, em segundos, que quem chama aceita esperar pela resposta inteira
    (complete) ou pelo primeiro trecho (stream). Estourado, a chamada termina em ModelUnavailable.
    """

    async def complete(self, capability: str, prompt: str, *, deadline: float,
                       max_tokens: int | None = None) -> str: ...

    def stream(self, capability: str, prompt: str, *, deadline: float,
               max_tokens: int | None = None) -> AsyncIterator[str]: ...


class TicketRepository(Protocol):
    """Fonte dos tickets usados no relatório."""

    def in_period(self, start: date, end: date) -> list[dict]: ...
