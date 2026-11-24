"""Contratos de que as features dependem. Só Protocols: nenhuma implementação mora aqui."""
from datetime import date
from typing import Protocol


class LanguageModel(Protocol):
    """Uma capacidade de linguagem pedida por nome lógico; quem escolhe o modelo físico é o gateway."""

    async def complete(self, capability: str, prompt: str, *, max_tokens: int | None = None) -> str: ...


class TicketRepository(Protocol):
    """Fonte dos tickets usados no relatório."""

    def in_period(self, start: date, end: date) -> list[dict]: ...
