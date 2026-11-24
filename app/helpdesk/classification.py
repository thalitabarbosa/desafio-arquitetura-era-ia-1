import json

from .errors import InvalidModelOutput
from .ports import LanguageModel
from .schemas import Classification, TicketInput

CATEGORIES = {"delivery", "payment", "exchange_return", "product_defect", "other"}
PRIORITIES = {"low", "medium", "high"}


class Classifier:
    """F1, síncrona: o cliente espera a confirmação na tela (ADR 0004)."""

    def __init__(self, model: LanguageModel, capability: str, deadline: float):
        self._model = model
        self._capability = capability
        self._deadline = deadline

    async def classify(self, ticket: TicketInput) -> Classification:
        text = await self._model.complete(self._capability, f"TASK: classify\n{ticket.text}",
                                          deadline=self._deadline)
        try:
            data = json.loads(text)
        except ValueError as err:
            raise InvalidModelOutput("Classificação não veio em JSON") from err
        if data.get("category") not in CATEGORIES or data.get("priority") not in PRIORITIES:
            raise InvalidModelOutput("Classificação fora dos valores permitidos")
        return Classification(ticket_id=ticket.ticket_id, category=data["category"], priority=data["priority"])
