from typing import Protocol
from openai import AsyncOpenAI
from groq import AsyncGroq

from app.config import OPENAI_MODEL_EXPENSIVE

class LLMProvider(Protocol):
    async def complete(self, prompt: str, model: str) -> str: ...


class OpenAILLMProvider:
    def __init__(self):
        from app.config import get_settings
        self._client = AsyncOpenAI(api_key=get_settings().openai_api_key)

    async def complete(self, prompt: str, model: str = OPENAI_MODEL_EXPENSIVE) -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )
        return response.choices[0].message.content


class GroqLLMProvider:
    def __init__(self):
        from app.config import get_settings
        self._client = AsyncGroq(api_key=get_settings().groq_api_key)

    async def complete(self, prompt: str, model: str = "llama-3.3-70b-versatile") -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )
        return response.choices[0].message.content


_openai: OpenAILLMProvider | None = None
_groq: GroqLLMProvider | None = None


class _LazyOpenAI:
    async def complete(self, prompt: str, model: str = OPENAI_MODEL_EXPENSIVE) -> str:
        global _openai
        if _openai is None:
            _openai = OpenAILLMProvider()
        return await _openai.complete(prompt, model)


class _LazyGroq:
    async def complete(self, prompt: str, model: str = "llama-3.3-70b-versatile") -> str:
        global _groq
        if _groq is None:
            _groq = GroqLLMProvider()
        return await _groq.complete(prompt, model)


# Lazy singletons — instantiated on first use, not at import time
openai_provider: LLMProvider = _LazyOpenAI()
groq_provider: LLMProvider = _LazyGroq()

# Alias used in profile_extractor (routed to OPENAI_MODEL_EXPENSIVE per the
# single-routing-layer rule in sonar/CLAUDE.md — originally hardcoded gpt-4o,
# migrated to the project-wide expensive-tier constant in the Wizard slice).
llm_client = openai_provider


def get_llm_client() -> LLMProvider:
    """FastAPI Depends() factory for the default LLM client. See #21."""
    return llm_client
