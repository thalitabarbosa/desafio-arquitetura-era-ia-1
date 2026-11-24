"""Ponto de composição da aplicação: lê o ambiente, monta adaptadores e features e expõe as rotas.

É o único componente que conhece as implementações concretas (adapters.*).
"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .adapters.gateway import GatewayLanguageModel
from .adapters.ticket_file import TicketFile
from .classification import Classifier
from .errors import InvalidModelOutput, InvalidPeriod, ModelUnavailable, QuotaExceeded, TicketSourceUnavailable
from .extraction import OrderExtractor
from .report import TopicsReporter
from .schemas import Classification, OrderData, PeriodInput, ReplySuggestion, TicketInput, TopicsReport
from .suggestion import ReplySuggester

# Capacidades lógicas (ADR 0003). O modelo físico por trás de cada uma está em gateway/config.yaml.
CAPABILITY_CLASSIFY = os.environ.get("CAPABILITY_CLASSIFY", "helpdesk-classify")
CAPABILITY_SUGGEST = os.environ.get("CAPABILITY_SUGGEST", "helpdesk-suggest")
CAPABILITY_EXTRACT = os.environ.get("CAPABILITY_EXTRACT", "helpdesk-extract")
CAPABILITY_TOPICS = os.environ.get("CAPABILITY_TOPICS", "helpdesk-topics")

MAX_OUTPUT_TOKENS = 2000
TICKETS_FILE = os.environ.get("TICKETS_FILE", "/data/tickets.jsonl")
TICKETS_PER_CALL = 150

gateway = GatewayLanguageModel(base_url=os.environ["GATEWAY_BASE_URL"], api_key=os.environ["GATEWAY_API_KEY"])
classifier = Classifier(gateway, CAPABILITY_CLASSIFY)
suggester = ReplySuggester(gateway, CAPABILITY_SUGGEST, MAX_OUTPUT_TOKENS)
extractor = OrderExtractor(gateway, CAPABILITY_EXTRACT)
reporter = TopicsReporter(gateway, TicketFile(TICKETS_FILE), CAPABILITY_TOPICS, TICKETS_PER_CALL, MAX_OUTPUT_TOKENS)

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


@app.post("/tickets/classification")
async def classify_ticket(ticket: TicketInput) -> Classification:
    return await classifier.classify(ticket)


@app.post("/tickets/reply-suggestion")
async def suggest_reply(ticket: TicketInput) -> ReplySuggestion:
    return await suggester.suggest(ticket)


@app.post("/tickets/extraction")
async def extract_order_data(ticket: TicketInput) -> OrderData:
    return await extractor.extract(ticket)


@app.post("/reports/topics")
async def topics_report(period: PeriodInput) -> TopicsReport:
    return await reporter.build(period)
