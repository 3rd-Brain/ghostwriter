from dataclasses import dataclass


@dataclass
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int


class BaseProvider:
    provider_name: str = ""

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        api_key: str | None = None,
    ) -> GenerationResult:
        raise NotImplementedError
