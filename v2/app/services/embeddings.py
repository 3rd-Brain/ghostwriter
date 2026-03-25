from openai import AsyncOpenAI

from app.config import settings


async def generate_embedding(text: str, api_key: str | None = None) -> list[float]:
    client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)
    response = await client.embeddings.create(
        input=text,
        model=settings.embedding_model,
    )
    return response.data[0].embedding
