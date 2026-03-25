import pytest
from app.providers.registry import resolve_provider
from app.providers.anthropic import AnthropicProvider
from app.providers.openai import OpenAIProvider
from app.providers.google import GoogleProvider


def test_resolve_anthropic():
    provider = resolve_provider("claude-haiku-4-5-20251001")
    assert isinstance(provider, AnthropicProvider)


def test_resolve_openai_gpt():
    provider = resolve_provider("gpt-4o")
    assert isinstance(provider, OpenAIProvider)


def test_resolve_openai_o1():
    provider = resolve_provider("o1-preview")
    assert isinstance(provider, OpenAIProvider)


def test_resolve_google():
    provider = resolve_provider("gemini-2.0-flash")
    assert isinstance(provider, GoogleProvider)


def test_resolve_unknown():
    with pytest.raises(ValueError, match="No provider found"):
        resolve_provider("unknown-model")


def test_provider_caching():
    p1 = resolve_provider("claude-haiku-4-5-20251001")
    p2 = resolve_provider("claude-sonnet-4-6")
    assert p1 is p2  # same instance cached by provider name
