from app.providers.base import BaseProvider
from app.providers.anthropic import AnthropicProvider
from app.providers.openai import OpenAIProvider
from app.providers.google import GoogleProvider

MODEL_PREFIX_MAP = {
    "claude-": AnthropicProvider,
    "gpt-": OpenAIProvider,
    "o1": OpenAIProvider,
    "o3": OpenAIProvider,
    "o4": OpenAIProvider,
    "gemini-": GoogleProvider,
}

_cache: dict[str, BaseProvider] = {}


def resolve_provider(model: str) -> BaseProvider:
    for prefix, provider_cls in MODEL_PREFIX_MAP.items():
        if model.startswith(prefix):
            if provider_cls.provider_name not in _cache:
                _cache[provider_cls.provider_name] = provider_cls()
            return _cache[provider_cls.provider_name]
    raise ValueError(f"No provider found for model: {model}")
