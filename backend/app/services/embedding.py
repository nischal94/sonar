from typing import Protocol
from openai import AsyncOpenAI
from app.config import get_settings

class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class OpenAIEmbeddingProvider:
    def __init__(self):
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


embedding_provider = OpenAIEmbeddingProvider()
