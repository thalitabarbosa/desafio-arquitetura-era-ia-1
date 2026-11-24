"""Contratos de que as features dependem. Nenhuma implementação mora aqui."""
from typing import Protocol


class LanguageModel(Protocol):
    """Uma capacidade de linguagem pedida por nome lógico; quem escolhe o modelo é a infraestrutura."""

    async def complete(self, capability: str, prompt: str, *, max_tokens: int | None = None) -> str: ...


class ModelUnavailable(Exception):
    """Nenhum modelo conseguiu atender a capacidade pedida."""


class InvalidModelOutput(Exception):
    """O modelo respondeu, mas fora do contrato da feature."""
