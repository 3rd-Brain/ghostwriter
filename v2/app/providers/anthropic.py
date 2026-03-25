import anthropic

from app.providers.base import BaseProvider, GenerationResult
from app.config import settings


class AnthropicProvider(BaseProvider):
    provider_name = "anthropic"

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        api_key: str | None = None,
    ) -> GenerationResult:
        client = anthropic.AsyncAnthropic(api_key=api_key or settings.anthropic_api_key)
        response = await client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return GenerationResult(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
