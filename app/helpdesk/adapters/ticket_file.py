"""Lê os tickets de data/tickets.jsonl (um JSON por linha)."""
import json
from datetime import date, datetime

from ..errors import TicketSourceUnavailable


class TicketFile:
    def __init__(self, path: str):
        self._path = path

    def in_period(self, start: date, end: date) -> list[dict]:
        selected = []
        try:
            with open(self._path, encoding="utf-8") as file:
                for line in file:
                    ticket = json.loads(line)
                    day = datetime.fromisoformat(ticket["created_at"]).date()
                    if start <= day <= end:
                        selected.append(ticket)
        except OSError as err:
            raise TicketSourceUnavailable(f"Base de tickets indisponível: {err}") from err
        return selected
