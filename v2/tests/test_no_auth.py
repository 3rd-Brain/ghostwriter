import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_no_auth_brands_crud(disable_auth, mock_embedding):
    """In no-auth mode, endpoints work without Authorization header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create brand without auth header
        resp = await client.post("/brands", json={
            "name": "Test Brand",
            "voice_guidelines": "Be friendly",
        })
        assert resp.status_code == 201
        brand_id = resp.json()["id"]

        # List brands
        resp = await client.get("/brands")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # Get brand
        resp = await client.get(f"/brands/{brand_id}")
        assert resp.status_code == 200

        # Delete brand
        resp = await client.delete(f"/brands/{brand_id}")
        assert resp.status_code == 204


@pytest.mark.asyncio
async def test_no_auth_accounts_returns_404(disable_auth):
    """In no-auth mode, POST /accounts returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/accounts", json={"name": "Test"})
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_auth_mode_requires_key(mock_embedding):
    """In auth mode (default in tests), requests without key are rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/brands")
        assert resp.status_code in (401, 403)
