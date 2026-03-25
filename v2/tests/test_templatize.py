from unittest.mock import AsyncMock, patch

from app.providers.base import GenerationResult


async def test_templatize(authed_client):
    fake_result = GenerationResult(text="[Hook] then [CTA]", input_tokens=50, output_tokens=30)
    fake_provider = AsyncMock()
    fake_provider.generate = AsyncMock(return_value=fake_result)
    fake_provider.provider_name = "anthropic"

    with patch("app.routers.templatize.resolve_provider", return_value=fake_provider):
        resp = await authed_client.post("/templatize", json={
            "content": "Just launched our new AI tool! Check it out at example.com",
        })
    assert resp.status_code == 200
    assert resp.json()["template"] == "[Hook] then [CTA]"
