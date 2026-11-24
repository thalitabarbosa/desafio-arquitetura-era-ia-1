"""Único componente que fala com o AI Gateway (API compatível com a da OpenAI).

A aplicação conhece só nomes lógicos de capacidade e a chave virtual dela no gateway; provider,
modelo físico, credenciais, retries e fallback são decididos no gateway (ADRs 0002, 0003, 0007).
"""
import openai
from openai import AsyncOpenAI

from ..errors import ModelUnavailable, QuotaExceeded


class GatewayLanguageModel:
    def __init__(self, base_url: str, api_key: str, timeout: float = 600.0):
        # Sem retries no SDK: retry mora em um lugar só, o gateway.
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)

    async def complete(self, capability: str, prompt: str, *, max_tokens: int | None = None) -> str:
        extra = {"max_tokens": max_tokens} if max_tokens else {}
        try:
            response = await self._client.chat.completions.create(
                model=capability, messages=[{"role": "user", "content": prompt}], **extra)
        except openai.APIError as err:
            raise translate(capability, err) from err
        return response.choices[0].message.content or ""


def translate(capability: str, err: openai.APIError) -> Exception:
    """Converte a falha do gateway num erro de domínio."""
    status = getattr(err, "status_code", None)
    text = str(err)
    if status == 429 or "budget" in text.lower():
        return QuotaExceeded(f"O gateway recusou '{capability}': {text}")
    return ModelUnavailable(f"Nenhum modelo atendeu '{capability}': {text}")
