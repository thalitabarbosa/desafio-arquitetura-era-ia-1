from collections.abc import AsyncIterator

from .ports import LanguageModel
from .schemas import TicketInput


class ReplySuggester:
    """F2, streaming: o atendente começa a ler e editar assim que o texto aparece (ADR 0004)."""

    def __init__(self, model: LanguageModel, capability: str, max_tokens: int, first_chunk_deadline: float):
        self._model = model
        self._capability = capability
        self._max_tokens = max_tokens
        self._deadline = first_chunk_deadline

    def stream(self, ticket: TicketInput) -> AsyncIterator[str]:
        return self._model.stream(self._capability, f"TASK: suggest\n{ticket.text}",
                                  deadline=self._deadline, max_tokens=self._max_tokens)
