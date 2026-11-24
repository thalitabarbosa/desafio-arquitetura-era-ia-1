"""Tarefas assíncronas do relatório de temas (Asynchronous Request-Reply, ADR 0004).

Estado em memória do processo: não sobrevive a um reinício da aplicação (fora do escopo).
"""
import asyncio
import uuid
from dataclasses import dataclass, field

from .errors import InvalidModelOutput, ModelUnavailable, QuotaExceeded, TicketSourceUnavailable
from .report import TopicsReporter, validate
from .schemas import PeriodInput, ReportStatus, TopicsReport

EXPECTED_FAILURES = (ModelUnavailable, QuotaExceeded, InvalidModelOutput, TicketSourceUnavailable)


@dataclass
class Job:
    id: str
    period: PeriodInput
    state: str = "pending"
    done: int = 0
    total: int | None = None
    reason: str | None = None
    result: TopicsReport | None = None
    task: asyncio.Task | None = field(default=None, repr=False)


class ReportJobs:
    def __init__(self, reporter: TopicsReporter):
        self._reporter = reporter
        self._jobs: dict[str, Job] = {}

    def submit(self, period: PeriodInput) -> Job:
        validate(period)  # período inválido é recusado na hora (422), sem criar tarefa
        job = Job(id=uuid.uuid4().hex[:12], period=period)
        self._jobs[job.id] = job
        job.task = asyncio.create_task(self._run(job))
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def status(self, job: Job) -> ReportStatus:
        progress = f"{job.done}/{job.total}" if job.total is not None else None
        return ReportStatus(state=job.state, progress=progress, reason=job.reason)

    async def _run(self, job: Job) -> None:
        job.state = "running"

        def progress(done: int, total: int) -> None:
            job.done, job.total = done, total

        try:
            job.result = await self._reporter.build(job.period, progress)
            job.state = "done"
        except EXPECTED_FAILURES as err:
            job.state, job.reason = "failed", str(err)
        except Exception as err:  # nunca deixar a tarefa presa em running
            job.state, job.reason = "failed", f"Erro inesperado: {err!r}"
