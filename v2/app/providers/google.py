from google import genai
from google.genai import types

from app.providers.base import BaseProvider, GenerationResult
from app.config import settings


class GoogleProvider(BaseProvider):
    provider_name = "google"

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        api_key: str | None = None,
    ) -> GenerationResult:
        client = genai.Client(api_key=api_key or settings.google_api_key)
        response = await client.aio.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return GenerationResult(
            text=response.text,
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
        )
