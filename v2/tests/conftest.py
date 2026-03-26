import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.config import settings

TEST_DATABASE_URL = settings.database_url.replace("/ghostwriter", "/ghostwriter_test")

test_engine = create_async_engine(TEST_DATABASE_URL)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def override_db():
    async def _get_test_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def enable_auth():
    """Tests run with auth enabled by default (original behavior)."""
    original = settings.auth_enabled
    settings.auth_enabled = True
    yield
    settings.auth_enabled = original


@pytest.fixture
def disable_auth():
    """Use this fixture to test no-auth mode."""
    original = settings.auth_enabled
    settings.auth_enabled = False
    yield
    settings.auth_enabled = original


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authed_client(client: AsyncClient):
    """Create an account and return a client with the API key set in headers."""
    resp = await client.post("/accounts", json={"name": "Test Account"})
    data = resp.json()
    api_key = data["api_key"]
    client.headers["Authorization"] = f"Bearer {api_key}"
    return client


@pytest.fixture
def mock_embedding():
    """Mock generate_embedding to return a fixed 1536-dim vector."""
    fake_embedding = [0.01] * 1536
    with patch("app.services.embeddings.generate_embedding", new_callable=AsyncMock, return_value=fake_embedding) as m:
        yield m


@pytest.fixture
def mock_provider():
    """Mock resolve_provider to return a fake provider."""
    from app.providers.base import GenerationResult

    fake_result = GenerationResult(text="Generated output", input_tokens=100, output_tokens=50)
    fake_provider = AsyncMock()
    fake_provider.generate = AsyncMock(return_value=fake_result)
    fake_provider.provider_name = "anthropic"

    with patch("app.engine.executor.resolve_provider", return_value=fake_provider) as m:
        yield m
