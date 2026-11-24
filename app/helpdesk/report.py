import json

from .errors import InvalidModelOutput, InvalidPeriod
from .ports import LanguageModel, TicketRepository
from .schemas import PeriodInput, Topic, TopicsReport


class TopicsReporter:
    def __init__(self, model: LanguageModel, tickets: TicketRepository, capability: str,
                 batch_size: int, max_tokens: int):
        self._model = model
        self._tickets = tickets
        self._capability = capability
        self._batch_size = batch_size
        self._max_tokens = max_tokens

    async def build(self, period: PeriodInput) -> TopicsReport:
        validate(period)
        selected = self._tickets.in_period(period.start, period.end)

        # O mês inteiro não cabe numa chamada: processa em lotes, um depois do outro.
        totals: dict[str, dict] = {}
        for first in range(0, len(selected), self._batch_size):
            batch = selected[first:first + self._batch_size]
            merge(totals, await self._topics_of(batch))
        return assemble(period, len(selected), totals)

    async def _topics_of(self, batch: list[dict]) -> list[dict]:
        content = "\n".join(f"[{t['id']}] {t['text']}" for t in batch)
        text = await self._model.complete(self._capability, f"TASK: topics\n{content}", max_tokens=self._max_tokens)
        try:
            return json.loads(text)["topics"]
        except (ValueError, KeyError) as err:
            raise InvalidModelOutput("Temas não vieram no formato esperado") from err


def validate(period: PeriodInput) -> None:
    if period.start > period.end:
        raise InvalidPeriod("A data inicial é posterior à data final")


def merge(totals: dict[str, dict], topics: list[dict]) -> None:
    for item in topics:
        current = totals.setdefault(item["topic"], {"count": 0, "examples": []})
        current["count"] += item["count"]
        current["examples"] = (current["examples"] + item["examples"])[:3]


def assemble(period: PeriodInput, total: int, totals: dict[str, dict]) -> TopicsReport:
    items = [Topic(topic=name, **data) for name, data in totals.items()]
    items.sort(key=lambda t: (-t.count, t.topic))
    return TopicsReport(start=period.start, end=period.end, total_tickets=total, topics=items)
