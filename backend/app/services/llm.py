from typing import Protocol
from openai import AsyncOpenAI
from groq import AsyncGroq

class LLMProvider(Protocol):
    async def complete(self, prompt: str, model: str) -> str: ...


class OpenAILLMProvider:
    def __init__(self):
        from app.config import get_settings
        self._client = AsyncOpenAI(api_key=get_settings().openai_api_key)

    async def complete(self, prompt: str, model: str = "gpt-4o") -> str:
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
    async def complete(self, prompt: str, model: str = "gpt-4o") -> str:
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

# Alias used in profile_extractor (always uses GPT-4o for quality)
llm_client = openai_provider
