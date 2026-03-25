from openai import AsyncOpenAI

from app.providers.base import BaseProvider, GenerationResult
from app.config import settings


class OpenAIProvider(BaseProvider):
    provider_name = "openai"

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        api_key: str | None = None,
    ) -> GenerationResult:
        client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return GenerationResult(
            text=response.choices[0].message.content or "",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
