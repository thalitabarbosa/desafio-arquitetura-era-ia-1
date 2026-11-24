"""Único componente que fala com o AI Gateway (API compatível com a da OpenAI).

A aplicação conhece só nomes lógicos de capacidade e a chave do próprio gateway; provider,
modelo físico, credenciais, retries e fallback são decididos no gateway.
"""
import openai
from openai import AsyncOpenAI

from ..ports import ModelUnavailable


class GatewayLanguageModel:
    def __init__(self, base_url: str, api_key: str, timeout: float = 600.0):
        # Sem retries no SDK: retry é responsabilidade de um lugar só (o gateway).
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)

    async def complete(self, capability: str, prompt: str, *, max_tokens: int | None = None) -> str:
        extra = {"max_tokens": max_tokens} if max_tokens else {}
        try:
            response = await self._client.chat.completions.create(
                model=capability, messages=[{"role": "user", "content": prompt}], **extra)
        except openai.APIError as err:
            raise ModelUnavailable(f"Gateway não atendeu '{capability}': {err}") from err
        return response.choices[0].message.content
