"""Único componente que fala com o AI Gateway (API compatível com a da OpenAI).

A aplicação conhece só nomes lógicos de capacidade e a chave virtual dela no gateway; provider,
modelo físico, credenciais, retries e fallback são decididos no gateway (ADRs 0002, 0003, 0007).
Aqui mora só o prazo que cada feature aceita esperar (ADR 0004).
"""
import asyncio
from collections.abc import AsyncIterator

import openai
from openai import AsyncOpenAI

from ..errors import ModelUnavailable, QuotaExceeded


class GatewayLanguageModel:
    def __init__(self, base_url: str, api_key: str, read_timeout: float):
        # Sem retries no SDK: retry mora em um lugar só, o gateway (retries em camadas se multiplicam).
        # read_timeout limita o silêncio entre dois trechos de um stream.
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=0, timeout=read_timeout)

    async def complete(self, capability: str, prompt: str, *, deadline: float,
                       max_tokens: int | None = None) -> str:
        try:
            async with asyncio.timeout(deadline):
                response = await self._client.chat.completions.create(
                    model=capability, messages=[{"role": "user", "content": prompt}],
                    timeout=deadline, **_max_tokens(max_tokens))
        except TimeoutError as err:
            raise ModelUnavailable(f"'{capability}' não respondeu em {deadline:g} s") from err
        except openai.APIError as err:
            raise translate(capability, err) from err
        return response.choices[0].message.content or ""

    async def stream(self, capability: str, prompt: str, *, deadline: float,
                     max_tokens: int | None = None) -> AsyncIterator[str]:
        try:
            async with asyncio.timeout(deadline):  # prazo até o primeiro trecho
                response = await self._client.chat.completions.create(
                    model=capability, messages=[{"role": "user", "content": prompt}], stream=True,
                    **_max_tokens(max_tokens))
                chunks = _texts(response)
                first = await anext(chunks, None)
        except TimeoutError as err:
            raise ModelUnavailable(f"'{capability}' não começou a responder em {deadline:g} s") from err
        except openai.APIError as err:
            raise translate(capability, err) from err
        if first is None:
            return
        yield first
        try:
            async for text in chunks:
                yield text
        except Exception as err:  # erro do gateway no meio do stream ou conexão perdida
            raise ModelUnavailable(f"'{capability}' interrompeu a geração: {err}") from err
        finally:
            await response.close()


async def _texts(response) -> AsyncIterator[str]:
    async for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def _max_tokens(max_tokens: int | None) -> dict:
    return {"max_tokens": max_tokens} if max_tokens else {}


def translate(capability: str, err: Exception) -> Exception:
    """Converte a falha do gateway num erro de domínio."""
    status = getattr(err, "status_code", None)
    text = str(err)
    if status == 429 or "budget" in text.lower():
        return QuotaExceeded(f"O gateway recusou '{capability}': {text}")
    return ModelUnavailable(f"Nenhum modelo atendeu '{capability}': {text}")
