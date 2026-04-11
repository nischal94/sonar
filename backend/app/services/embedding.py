from typing import Protocol
from openai import AsyncOpenAI

class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class OpenAIEmbeddingProvider:
    def __init__(self):
        from app.config import get_settings
        self._client = AsyncOpenAI(api_key=get_settings().openai_api_key)
        self.model = "text-embedding-3-small"
        self.dimensions = 1536

    async def embed(self, text: str) -> list[float]:
        # Truncate to 8000 chars to stay within token limits
        text = text[:8000]
        response = await self._client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding


_provider: OpenAIEmbeddingProvider | None = None


class _LazyEmbeddingProvider:
    """Defers OpenAI client instantiation until first use."""
    async def embed(self, text: str) -> list[float]:
        global _provider
        if _provider is None:
            _provider = OpenAIEmbeddingProvider()
        return await _provider.embed(text)


embedding_provider: EmbeddingProvider = _LazyEmbeddingProvider()


def get_embedding_provider() -> EmbeddingProvider:
    """FastAPI Depends() factory. Tests use
    `app.dependency_overrides[get_embedding_provider] = lambda: fake` instead
    of patching module globals — impossible to defeat with `from ... import ...`
    because the override layer sits above Python's import binding. See #21."""
    return embedding_provider
