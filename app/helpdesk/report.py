import asyncio
import json
from collections.abc import Callable

from .errors import InvalidModelOutput, InvalidPeriod
from .ports import LanguageModel, TicketRepository
from .schemas import PeriodInput, Topic, TopicsReport

Progress = Callable[[int, int], None]


class TopicsReporter:
    """F3, assíncrona: ninguém espera olhando; o painel consulta o status depois (ADR 0004)."""

    def __init__(self, model: LanguageModel, tickets: TicketRepository, capability: str, *,
                 batch_size: int, max_tokens: int, concurrency: int, call_deadline: float):
        self._model = model
        self._tickets = tickets
        self._capability = capability
        self._batch_size = batch_size
        self._max_tokens = max_tokens
        self._concurrency = concurrency
        self._deadline = call_deadline

    async def build(self, period: PeriodInput, on_progress: Progress = lambda done, total: None) -> TopicsReport:
        validate(period)
        selected = self._tickets.in_period(period.start, period.end)
        total = len(selected)
        on_progress(0, total)

        # O mês inteiro não cabe numa chamada: lotes, alguns em paralelo. O resultado é juntado
        # na ordem dos lotes, então é o mesmo do processamento sequencial.
        batches = [selected[i:i + self._batch_size] for i in range(0, total, self._batch_size)]
        slots = asyncio.Semaphore(self._concurrency)
        done = 0

        async def run(batch: list[dict]) -> list[dict]:
            nonlocal done
            async with slots:
                topics = await self._topics_of(batch)
            done += len(batch)
            on_progress(done, total)
            return topics

        tasks = [asyncio.create_task(run(batch)) for batch in batches]
        try:
            results = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:  # falhou um lote: o relatório falha e os outros lotes são cancelados
                task.cancel()
            raise

        totals: dict[str, dict] = {}
        for topics in results:
            merge(totals, topics)
        return assemble(period, total, totals)

    async def _topics_of(self, batch: list[dict]) -> list[dict]:
        content = "\n".join(f"[{t['id']}] {t['text']}" for t in batch)
        text = await self._model.complete(self._capability, f"TASK: topics\n{content}",
                                          deadline=self._deadline, max_tokens=self._max_tokens)
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
