import json
import re

from .errors import InvalidModelOutput
from .ports import LanguageModel
from .schemas import OrderData, TicketInput

ORDER_FORMAT = re.compile(r"^#\d{6}$")


class OrderExtractor:
    """F4, síncrona: alimenta uma automação de troca sem revisão humana (ADRs 0004 e 0007)."""

    def __init__(self, model: LanguageModel, capability: str, deadline: float):
        self._model = model
        self._capability = capability
        self._deadline = deadline

    async def extract(self, ticket: TicketInput) -> OrderData:
        text = await self._model.complete(self._capability, f"TASK: extract\n{ticket.text}",
                                          deadline=self._deadline)
        try:
            data = json.loads(text)
        except ValueError as err:
            raise InvalidModelOutput("Extração não veio em JSON") from err
        order_number = data.get("order_number")
        if order_number is not None and not ORDER_FORMAT.match(order_number):
            raise InvalidModelOutput("Número de pedido em formato inválido")
        return OrderData(ticket_id=ticket.ticket_id, order_number=order_number, product=data.get("product"))
