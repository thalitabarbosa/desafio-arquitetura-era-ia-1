"""Ponto de composição da aplicação: lê o ambiente, monta adaptadores e features e expõe as rotas.

É o único componente que conhece as implementações concretas (adapters.*). Modos de execução
por feature: ADR 0004.
"""
import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from .adapters.gateway import GatewayLanguageModel
from .adapters.ticket_file import TicketFile
from .classification import Classifier
from .errors import InvalidModelOutput, InvalidPeriod, ModelUnavailable, QuotaExceeded, TicketSourceUnavailable
from .extraction import OrderExtractor
from .jobs import ReportJobs
from .report import TopicsReporter
from .schemas import Classification, OrderData, PeriodInput, ReportAccepted, TicketInput, TopicsReport
from .suggestion import ReplySuggester


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# Capacidades lógicas (ADR 0003). O modelo físico por trás de cada uma está em gateway/config.yaml.
CAPABILITY_CLASSIFY = env("CAPABILITY_CLASSIFY", "helpdesk-classify")
CAPABILITY_SUGGEST = env("CAPABILITY_SUGGEST", "helpdesk-suggest")
CAPABILITY_EXTRACT = env("CAPABILITY_EXTRACT", "helpdesk-extract")
CAPABILITY_TOPICS = env("CAPABILITY_TOPICS", "helpdesk-topics")

# Prazos do lado da aplicação, em segundos (ADRs 0004 e 0007). Ficam abaixo dos 30 s da borda
# e acima da soma de tentativas que o gateway faz antes de cair no fallback.
SYNC_DEADLINE = float(env("SYNC_DEADLINE_S", "12"))          # F1 e F4: resposta inteira
STREAM_DEADLINE = float(env("STREAM_DEADLINE_S", "14"))      # F2: até o 1º trecho e entre trechos
REPORT_CALL_DEADLINE = float(env("REPORT_CALL_DEADLINE_S", "50"))  # F3: cada lote
REPORT_CONCURRENCY = int(env("REPORT_CONCURRENCY", "4"))
REPORT_RETRY_AFTER = env("REPORT_RETRY_AFTER_S", "5")

MAX_OUTPUT_TOKENS = 2000
TICKETS_FILE = env("TICKETS_FILE", "/data/tickets.jsonl")
TICKETS_PER_CALL = 150

gateway = GatewayLanguageModel(env("GATEWAY_BASE_URL", "http://gateway:4000/v1"), os.environ["GATEWAY_API_KEY"],
                               read_timeout=STREAM_DEADLINE)
classifier = Classifier(gateway, CAPABILITY_CLASSIFY, SYNC_DEADLINE)
suggester = ReplySuggester(gateway, CAPABILITY_SUGGEST, MAX_OUTPUT_TOKENS, STREAM_DEADLINE)
extractor = OrderExtractor(gateway, CAPABILITY_EXTRACT, SYNC_DEADLINE)
reporter = TopicsReporter(gateway, TicketFile(TICKETS_FILE), CAPABILITY_TOPICS, batch_size=TICKETS_PER_CALL,
                          max_tokens=MAX_OUTPUT_TOKENS, concurrency=REPORT_CONCURRENCY,
                          call_deadline=REPORT_CALL_DEADLINE)
report_jobs = ReportJobs(reporter)

app = FastAPI(title="Helpdesk")

ERROR_STATUS = {
    InvalidPeriod: 422,
    InvalidModelOutput: 502,
    QuotaExceeded: 429,
    ModelUnavailable: 503,
    TicketSourceUnavailable: 503,
}


def domain_error(request: Request, err: Exception) -> JSONResponse:
    return JSONResponse(status_code=ERROR_STATUS[type(err)], content={"detail": str(err)})


for error_type in ERROR_STATUS:
    app.add_exception_handler(error_type, domain_error)


@app.get("/health")
def health():
    return {"status": "ok"}


# F1: síncrona.
@app.post("/tickets/classification")
async def classify_ticket(ticket: TicketInput) -> Classification:
    return await classifier.classify(ticket)


# F2: streaming (SSE).
def sse(data: dict, event: str | None = None) -> str:
    head = f"event: {event}\n" if event else ""
    return f"{head}data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/tickets/reply-suggestion")
async def suggest_reply(ticket: TicketInput) -> StreamingResponse:
    chunks = suggester.stream(ticket)
    # Falha antes do primeiro trecho ainda pode virar status HTTP (503/429) pelo handler de erros.
    first = await anext(chunks, None)

    async def events():
        try:
            if first is not None:
                yield sse({"chunk": first})
            async for piece in chunks:
                yield sse({"chunk": piece})
        except (ModelUnavailable, QuotaExceeded):
            # O 200 já foi enviado: a falha vira um evento dentro do próprio stream.
            yield sse({"ticket_id": ticket.ticket_id, "message": "A geração foi interrompida"}, event="error")
            return
        yield sse({"ticket_id": ticket.ticket_id}, event="end")

    # X-Accel-Buffering: sem ele, a borda (nginx) acumula a resposta e entrega tudo no fim.
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# F4: síncrona.
@app.post("/tickets/extraction")
async def extract_order_data(ticket: TicketInput) -> OrderData:
    return await extractor.extract(ticket)


# F3: Asynchronous Request-Reply.
@app.post("/reports/topics", status_code=202)
async def request_topics_report(period: PeriodInput) -> JSONResponse:
    job = report_jobs.submit(period)
    return JSONResponse(status_code=202, content=ReportAccepted(job_id=job.id, state=job.state).model_dump(),
                        headers={"Location": f"/reports/topics/status/{job.id}", "Retry-After": REPORT_RETRY_AFTER})


@app.get("/reports/topics/status/{job_id}")
async def topics_report_status(job_id: str):
    job = report_jobs.get(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"detail": "Relatório não encontrado"})
    if job.state == "done":
        return RedirectResponse(url=f"/reports/topics/{job.id}", status_code=303)
    headers = {"Retry-After": REPORT_RETRY_AFTER} if job.state in ("pending", "running") else {}
    return JSONResponse(content=report_jobs.status(job).model_dump(exclude_none=True), headers=headers)


@app.get("/reports/topics/{job_id}")
async def topics_report_result(job_id: str) -> TopicsReport:
    job = report_jobs.get(job_id)
    if job is None or job.result is None:
        return JSONResponse(status_code=404, content={"detail": "Relatório não encontrado ou ainda não concluído"})
    return job.result
