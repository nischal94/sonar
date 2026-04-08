from typing import Protocol
from openai import AsyncOpenAI
from groq import AsyncGroq
from app.config import get_settings

class LLMProvider(Protocol):
    async def complete(self, prompt: str, model: str) -> str: ...


class OpenAILLMProvider:
    def __init__(self):
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
        self._client = AsyncGroq(api_key=get_settings().groq_api_key)

    async def complete(self, prompt: str, model: str = "llama-3.3-70b-versatile") -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )
        return response.choices[0].message.content


# Default instances — swap via config if needed
openai_provider = OpenAILLMProvider()
groq_provider = GroqLLMProvider()

# Alias used in profile_extractor (always uses GPT-4o for quality)
llm_client = openai_provider
