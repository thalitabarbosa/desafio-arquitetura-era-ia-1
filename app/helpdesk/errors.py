"""Erros de domínio. As features e os adaptadores falam por eles; main.py os traduz para HTTP."""


class ModelUnavailable(Exception):
    """Nenhum modelo conseguiu atender a capacidade pedida (falha, timeout, sem fallback)."""


class QuotaExceeded(Exception):
    """O gateway recusou a chamada por governança (orçamento ou limite de requisições)."""


class InvalidModelOutput(Exception):
    """O modelo respondeu, mas fora do contrato da feature."""


class InvalidPeriod(Exception):
    """Período de relatório inválido."""


class TicketSourceUnavailable(Exception):
    """A base de tickets não pôde ser lida."""
