from .ports import LanguageModel
from .schemas import ReplySuggestion, TicketInput


class ReplySuggester:
    def __init__(self, model: LanguageModel, capability: str, max_tokens: int):
        self._model = model
        self._capability = capability
        self._max_tokens = max_tokens

    async def suggest(self, ticket: TicketInput) -> ReplySuggestion:
        text = await self._model.complete(self._capability, f"TASK: suggest\n{ticket.text}",
                                          max_tokens=self._max_tokens)
        return ReplySuggestion(ticket_id=ticket.ticket_id, suggestion=text)
