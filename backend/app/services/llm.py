from typing import Protocol
from openai import AsyncOpenAI
from groq import AsyncGroq

from app.config import OPENAI_MODEL_EXPENSIVE


class LLMProvider(Protocol):
    async def complete(
        self,
        prompt: str,
        model: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> str: ...


def _build_messages(prompt: str, system: str | None) -> list[dict]:
    """Topologically separates system from user content at the API boundary so
    user input (in `prompt`) cannot spoof the system role via delimiter-like
    strings (e.g. `<|system|>`). Required by sonar/CLAUDE.md 'Prompt injection
    defense is mandatory' — user input belongs ONLY in the user-role message.
    """
    if system is None:
        return [{"role": "user", "content": prompt}]
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]


class OpenAILLMProvider:
    def __init__(self):
        from app.config import get_settings

        self._client = AsyncOpenAI(api_key=get_settings().openai_api_key)

    async def complete(
        self,
        prompt: str,
        model: str = OPENAI_MODEL_EXPENSIVE,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        # OpenAI renamed `max_tokens` → `max_completion_tokens` for the gpt-5+
        # model generation (including gpt-5.4-mini). The old parameter name is
        # hard-rejected. Keep the Python kwarg named max_tokens for caller
        # stability; translate at the API boundary.
        response = await self._client.chat.completions.create(
            model=model,
            messages=_build_messages(prompt, system),
            temperature=0.3,
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content


class GroqLLMProvider:
    def __init__(self):
        from app.config import get_settings

        self._client = AsyncGroq(api_key=get_settings().groq_api_key)

    async def complete(
        self,
        prompt: str,
        model: str = "llama-3.3-70b-versatile",
        *,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=_build_messages(prompt, system),
            temperature=0.3,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content


_openai: OpenAILLMProvider | None = None
_groq: GroqLLMProvider | None = None


class _LazyOpenAI:
    async def complete(
        self,
        prompt: str,
        model: str = OPENAI_MODEL_EXPENSIVE,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        global _openai
        if _openai is None:
            _openai = OpenAILLMProvider()
        return await _openai.complete(
            prompt, model, system=system, max_tokens=max_tokens
        )


class _LazyGroq:
    async def complete(
        self,
        prompt: str,
        model: str = "llama-3.3-70b-versatile",
        *,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        global _groq
        if _groq is None:
            _groq = GroqLLMProvider()
        return await _groq.complete(prompt, model, system=system, max_tokens=max_tokens)


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
