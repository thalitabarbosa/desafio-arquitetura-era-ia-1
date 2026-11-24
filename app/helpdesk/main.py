import os

from fastapi import FastAPI, HTTPException

from . import extraction, report, suggestion
from .adapters.gateway import GatewayLanguageModel
from .classification import Classifier
from .ports import InvalidModelOutput, ModelUnavailable
from .schemas import (Classification, OrderData, PeriodInput, ReplySuggestion, TicketInput,
                      TopicsReport)

app = FastAPI(title="Helpdesk")

# Piloto: só a classificação passa pelo gateway.
gateway = GatewayLanguageModel(base_url=os.environ["GATEWAY_BASE_URL"], api_key=os.environ["GATEWAY_API_KEY"])
classifier = Classifier(gateway, os.environ.get("CAPABILITY_CLASSIFY", "helpdesk-classify"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tickets/classification")
async def classify_ticket(ticket: TicketInput) -> Classification:
    try:
        return await classifier.classify(ticket)
    except InvalidModelOutput as err:
        raise HTTPException(status_code=502, detail=str(err))
    except ModelUnavailable as err:
        raise HTTPException(status_code=503, detail=str(err))


@app.post("/tickets/reply-suggestion")
def suggest_reply(ticket: TicketInput) -> ReplySuggestion:
    return suggestion.suggest(ticket)


@app.post("/tickets/extraction")
def extract_order_data(ticket: TicketInput) -> OrderData:
    return extraction.extract(ticket)


@app.post("/reports/topics")
def topics_report(period: PeriodInput) -> TopicsReport:
    return report.topics(period)
