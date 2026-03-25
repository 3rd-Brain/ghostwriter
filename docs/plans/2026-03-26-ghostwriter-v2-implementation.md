# Ghostwriter V2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a clean, maintainable FastAPI service with PostgreSQL+pgvector that provides multi-step AI content generation as tool-callable API endpoints.

**Architecture:** Stateless FastAPI app with SQLAlchemy models, Alembic migrations, and a sequential workflow engine that resolves inputs (vector search, brand voice) then executes multi-step AI generation across Anthropic/OpenAI/Google providers. Dockerized with PostgreSQL+pgvector.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), asyncpg, Alembic, pgvector, Pydantic v2, Docker Compose, httpx (for Apify), anthropic SDK, openai SDK, google-genai SDK

---

### Task 1: Project Scaffolding & Docker

**Files:**
- Create: `v2/Dockerfile`
- Create: `v2/docker-compose.yml`
- Create: `v2/requirements.txt`
- Create: `v2/app/__init__.py`
- Create: `v2/app/main.py`
- Create: `v2/app/config.py`
- Create: `v2/tests/__init__.py`
- Create: `v2/.env.example`

**Step 1: Create requirements.txt**

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.30.0
alembic==1.13.0
pgvector==0.3.6
pydantic==2.9.0
pydantic-settings==2.5.0
python-multipart==0.0.12
anthropic==0.40.0
openai==1.55.0
google-genai==1.14.0
httpx==0.27.0
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
PyMuPDF==1.24.0
python-docx==1.1.0
markdown==3.7
pytest==8.3.0
pytest-asyncio==0.24.0
httpx==0.27.0
```

**Step 2: Create config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ghostwriter:ghostwriter@db:5432/ghostwriter"

    # System-level fallback API keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # Apify for Twitter scraping
    apify_api_token: str = ""

    # Embedding model
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    model_config = {"env_file": ".env"}


settings = Settings()
```

**Step 3: Create main.py**

```python
from fastapi import FastAPI

app = FastAPI(title="Ghostwriter V2", version="2.0.0")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 4: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 5: Create docker-compose.yml**

```yaml
services:
  db:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_USER: ghostwriter
      POSTGRES_PASSWORD: ghostwriter
      POSTGRES_DB: ghostwriter
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db
    volumes:
      - .:/app

volumes:
  pgdata:
```

**Step 6: Create .env.example**

```
DATABASE_URL=postgresql+asyncpg://ghostwriter:ghostwriter@db:5432/ghostwriter
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
APIFY_API_TOKEN=
```

**Step 7: Boot up Docker Compose and verify health endpoint**

Run: `cd v2 && docker compose up --build -d && sleep 5 && curl http://localhost:8000/health`
Expected: `{"status":"ok"}`

**Step 8: Commit**

```bash
git add v2/
git commit -m "feat(v2): project scaffolding with Docker, FastAPI, and PostgreSQL"
```

---

### Task 2: Database Setup & Alembic Migrations

**Files:**
- Create: `v2/app/database.py`
- Create: `v2/app/models/__init__.py`
- Create: `v2/app/models/account.py`
- Create: `v2/app/models/brand_voice.py`
- Create: `v2/app/models/workflow.py`
- Create: `v2/app/models/template.py`
- Create: `v2/app/models/source_content.py`
- Create: `v2/app/models/generated_content.py`
- Create: `v2/alembic/env.py`
- Create: `v2/alembic.ini`

**Step 1: Create database.py with async engine and session**

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

**Step 2: Create all SQLAlchemy models**

`app/models/account.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="account", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), __import__('sqlalchemy').ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, default="default")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    account: Mapped["Account"] = relationship(back_populates="api_keys")
```

`app/models/brand_voice.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BrandVoice(Base):
    __tablename__ = "brand_voices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    voice_guidelines: Mapped[str] = mapped_column(Text, nullable=False)
    sample_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

`app/models/workflow.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

`app/models/template.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.database import Base

import enum


class TemplateCategory(str, enum.Enum):
    short_form = "short_form"
    atomic = "atomic"
    mid_form = "mid_form"


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[TemplateCategory] = mapped_column(SAEnum(TemplateCategory), default=TemplateCategory.short_form)
    embedding = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

`app/models/source_content.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.database import Base


class SourceContent(Base):
    __tablename__ = "source_content"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, default="manual")
    channel_source: Mapped[str] = mapped_column(String, default="manual")
    embedding = mapped_column(Vector(1536), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

`app/models/generated_content.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GeneratedContent(Base):
    __tablename__ = "generated_content"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("brand_voices.id"), nullable=True)
    input_content: Mapped[str] = mapped_column(Text, default="")
    input_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str] = mapped_column(Text, nullable=False)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

`app/models/__init__.py`:
```python
from app.models.account import Account, ApiKey
from app.models.brand_voice import BrandVoice
from app.models.workflow import Workflow
from app.models.template import Template, TemplateCategory
from app.models.source_content import SourceContent
from app.models.generated_content import GeneratedContent

__all__ = [
    "Account", "ApiKey",
    "BrandVoice",
    "Workflow",
    "Template", "TemplateCategory",
    "SourceContent",
    "GeneratedContent",
]
```

**Step 3: Initialize Alembic**

Run inside the api container:
```bash
cd v2 && alembic init alembic
```

Then update `alembic/env.py` to use async engine and import all models:

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.config import settings
from app.database import Base
from app.models import *  # noqa: F401, F403 - import all models for autogenerate

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Update `alembic.ini` to set `sqlalchemy.url` to empty (overridden by env.py):
```ini
sqlalchemy.url =
```

**Step 4: Generate and run initial migration**

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

**Step 5: Verify tables exist**

```bash
docker compose exec db psql -U ghostwriter -c "\dt"
```
Expected: See accounts, api_keys, brand_voices, workflows, templates, source_content, generated_content tables.

**Step 6: Commit**

```bash
git add v2/
git commit -m "feat(v2): database models and initial Alembic migration"
```

---

### Task 3: Auth System (API Key Authentication)

**Files:**
- Create: `v2/app/auth/__init__.py`
- Create: `v2/app/auth/dependencies.py`
- Create: `v2/app/auth/service.py`
- Create: `v2/app/routers/__init__.py`
- Create: `v2/app/routers/accounts.py`
- Create: `v2/app/schemas/__init__.py`
- Create: `v2/app/schemas/account.py`
- Create: `v2/tests/test_auth.py`

**Step 1: Write failing test for API key auth**

```python
# tests/test_auth.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/brands")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_api_key_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/brands", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
```

**Step 2: Run test to verify it fails**

Run: `cd v2 && python -m pytest tests/test_auth.py -v`
Expected: FAIL (no /brands route yet)

**Step 3: Create auth service and dependency**

`app/auth/service.py`:
```python
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, ApiKey


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    return f"gw_{secrets.token_urlsafe(32)}"


async def create_account_with_key(db: AsyncSession, name: str, key_label: str = "default") -> tuple[Account, str]:
    account = Account(name=name)
    db.add(account)
    await db.flush()

    raw_key = generate_api_key()
    api_key = ApiKey(account_id=account.id, key_hash=hash_api_key(raw_key), label=key_label)
    db.add(api_key)
    await db.commit()
    await db.refresh(account)
    return account, raw_key


async def authenticate(db: AsyncSession, raw_key: str) -> Account | None:
    key_hash = hash_api_key(raw_key)
    stmt = (
        select(Account)
        .join(ApiKey)
        .where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

`app/auth/dependencies.py`:
```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.service import authenticate
from app.models.account import Account

security = HTTPBearer()


async def get_current_account(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
) -> Account:
    account = await authenticate(db, credentials.credentials)
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return account
```

`app/auth/__init__.py`:
```python
from app.auth.dependencies import get_current_account
from app.auth.service import create_account_with_key, generate_api_key, hash_api_key

__all__ = ["get_current_account", "create_account_with_key", "generate_api_key", "hash_api_key"]
```

**Step 4: Create account schemas and router**

`app/schemas/account.py`:
```python
import uuid
from datetime import datetime
from pydantic import BaseModel


class AccountCreate(BaseModel):
    name: str


class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountCreateResponse(BaseModel):
    account: AccountResponse
    api_key: str  # only returned once at creation
```

`app/routers/accounts.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_account, create_account_with_key
from app.schemas.account import AccountCreate, AccountCreateResponse, AccountResponse
from app.models.account import Account

router = APIRouter(tags=["accounts"])


@router.post("/accounts", response_model=AccountCreateResponse, status_code=201)
async def create_account(body: AccountCreate, db: AsyncSession = Depends(get_db)):
    account, raw_key = await create_account_with_key(db, body.name)
    return AccountCreateResponse(
        account=AccountResponse.model_validate(account),
        api_key=raw_key,
    )


@router.get("/accounts/me", response_model=AccountResponse)
async def get_me(account: Account = Depends(get_current_account)):
    return AccountResponse.model_validate(account)
```

**Step 5: Wire routers into main.py**

```python
from fastapi import FastAPI

from app.routers import accounts

app = FastAPI(title="Ghostwriter V2", version="2.0.0")

app.include_router(accounts.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 6: Run tests to verify they pass**

Run: `cd v2 && python -m pytest tests/test_auth.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add v2/
git commit -m "feat(v2): API key auth system with account creation"
```

---

### Task 4: Brand Voice CRUD

**Files:**
- Create: `v2/app/schemas/brand_voice.py`
- Create: `v2/app/routers/brands.py`
- Create: `v2/app/services/__init__.py`
- Create: `v2/tests/test_brands.py`

**Step 1: Write failing tests**

```python
# tests/test_brands.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_create_and_list_brands():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create account
        resp = await client.post("/accounts", json={"name": "Test"})
        api_key = resp.json()["api_key"]
        headers = {"Authorization": f"Bearer {api_key}"}

        # Create brand
        resp = await client.post("/brands", json={
            "name": "TestBrand",
            "voice_guidelines": "Speak casually",
        }, headers=headers)
        assert resp.status_code == 201
        brand_id = resp.json()["id"]

        # List brands
        resp = await client.get("/brands", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # Get single brand
        resp = await client.get(f"/brands/{brand_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "TestBrand"

        # Update brand
        resp = await client.put(f"/brands/{brand_id}", json={
            "voice_guidelines": "Speak formally"
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["voice_guidelines"] == "Speak formally"

        # Delete brand
        resp = await client.delete(f"/brands/{brand_id}", headers=headers)
        assert resp.status_code == 204
```

**Step 2: Run test to verify it fails**

Run: `cd v2 && python -m pytest tests/test_brands.py -v`
Expected: FAIL

**Step 3: Create schemas**

`app/schemas/brand_voice.py`:
```python
import uuid
from datetime import datetime
from pydantic import BaseModel


class BrandVoiceCreate(BaseModel):
    name: str
    voice_guidelines: str
    sample_content: str | None = None


class BrandVoiceUpdate(BaseModel):
    name: str | None = None
    voice_guidelines: str | None = None
    sample_content: str | None = None


class BrandVoiceResponse(BaseModel):
    id: uuid.UUID
    name: str
    voice_guidelines: str
    sample_content: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

**Step 4: Create router**

`app/routers/brands.py`:
```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_account
from app.models.account import Account
from app.models.brand_voice import BrandVoice
from app.schemas.brand_voice import BrandVoiceCreate, BrandVoiceUpdate, BrandVoiceResponse

router = APIRouter(tags=["brands"])


@router.post("/brands", response_model=BrandVoiceResponse, status_code=201)
async def create_brand(
    body: BrandVoiceCreate,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    brand = BrandVoice(account_id=account.id, **body.model_dump())
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return brand


@router.get("/brands", response_model=list[BrandVoiceResponse])
async def list_brands(
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BrandVoice).where(BrandVoice.account_id == account.id))
    return result.scalars().all()


@router.get("/brands/{brand_id}", response_model=BrandVoiceResponse)
async def get_brand(
    brand_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    brand = await db.get(BrandVoice, brand_id)
    if not brand or brand.account_id != account.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.put("/brands/{brand_id}", response_model=BrandVoiceResponse)
async def update_brand(
    brand_id: uuid.UUID,
    body: BrandVoiceUpdate,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    brand = await db.get(BrandVoice, brand_id)
    if not brand or brand.account_id != account.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(brand, field, value)
    await db.commit()
    await db.refresh(brand)
    return brand


@router.delete("/brands/{brand_id}", status_code=204)
async def delete_brand(
    brand_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    brand = await db.get(BrandVoice, brand_id)
    if not brand or brand.account_id != account.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    await db.delete(brand)
    await db.commit()
```

**Step 5: Register router in main.py**

Add `from app.routers import brands` and `app.include_router(brands.router)`.

**Step 6: Run tests**

Run: `cd v2 && python -m pytest tests/test_brands.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add v2/
git commit -m "feat(v2): brand voice CRUD endpoints"
```

---

### Task 5: Workflow CRUD

**Files:**
- Create: `v2/app/schemas/workflow.py`
- Create: `v2/app/routers/workflows.py`
- Create: `v2/tests/test_workflows.py`

**Step 1: Write failing tests**

```python
# tests/test_workflows.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

SAMPLE_STEPS = [
    {
        "order": 1,
        "name": "generate",
        "model": "claude-sonnet-4-20250514",
        "system_prompt": "You are a writer.",
        "user_prompt": "Write about: {content}",
        "max_tokens": 1024,
        "temperature": 0.7,
    }
]


@pytest.mark.asyncio
async def test_workflow_crud():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/accounts", json={"name": "Test"})
        api_key = resp.json()["api_key"]
        headers = {"Authorization": f"Bearer {api_key}"}

        # Create
        resp = await client.post("/workflows", json={
            "name": "Test Flow",
            "description": "A test workflow",
            "steps": SAMPLE_STEPS,
        }, headers=headers)
        assert resp.status_code == 201
        wf_id = resp.json()["id"]

        # List (should include system + user workflows)
        resp = await client.get("/workflows", headers=headers)
        assert resp.status_code == 200

        # Get
        resp = await client.get(f"/workflows/{wf_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["steps"][0]["model"] == "claude-sonnet-4-20250514"

        # Update
        resp = await client.put(f"/workflows/{wf_id}", json={
            "description": "Updated"
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated"

        # Delete
        resp = await client.delete(f"/workflows/{wf_id}", headers=headers)
        assert resp.status_code == 204
```

**Step 2: Run test to verify it fails**

Run: `cd v2 && python -m pytest tests/test_workflows.py -v`
Expected: FAIL

**Step 3: Create schemas**

`app/schemas/workflow.py`:
```python
import uuid
from datetime import datetime
from pydantic import BaseModel


class WorkflowStep(BaseModel):
    order: int
    name: str
    model: str
    system_prompt: str
    user_prompt: str
    max_tokens: int = 4096
    temperature: float = 0.7


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    steps: list[WorkflowStep]


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[WorkflowStep] | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    name: str
    description: str
    steps: list[WorkflowStep]
    created_at: datetime

    model_config = {"from_attributes": True}
```

**Step 4: Create router**

`app/routers/workflows.py` — follows same pattern as brands. List endpoint returns both system workflows (`account_id IS NULL`) and user workflows. Users can only modify their own workflows.

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_account
from app.models.account import Account
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse

router = APIRouter(tags=["workflows"])


@router.post("/workflows", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    workflow = Workflow(
        account_id=account.id,
        name=body.name,
        description=body.description,
        steps=[s.model_dump() for s in body.steps],
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.get("/workflows", response_model=list[WorkflowResponse])
async def list_workflows(
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(
            or_(Workflow.account_id == account.id, Workflow.account_id.is_(None))
        )
    )
    return result.scalars().all()


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    wf = await db.get(Workflow, workflow_id)
    if not wf or (wf.account_id is not None and wf.account_id != account.id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.put("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowUpdate,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    wf = await db.get(Workflow, workflow_id)
    if not wf or wf.account_id != account.id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    update_data = body.model_dump(exclude_unset=True)
    if "steps" in update_data and update_data["steps"] is not None:
        update_data["steps"] = [s.model_dump() for s in body.steps]
    for field, value in update_data.items():
        setattr(wf, field, value)
    await db.commit()
    await db.refresh(wf)
    return wf


@router.delete("/workflows/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    wf = await db.get(Workflow, workflow_id)
    if not wf or wf.account_id != account.id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(wf)
    await db.commit()
```

**Step 5: Register router, run tests**

Run: `cd v2 && python -m pytest tests/test_workflows.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add v2/
git commit -m "feat(v2): workflow CRUD endpoints"
```

---

### Task 6: AI Provider Layer

**Files:**
- Create: `v2/app/providers/__init__.py`
- Create: `v2/app/providers/base.py`
- Create: `v2/app/providers/anthropic.py`
- Create: `v2/app/providers/openai.py`
- Create: `v2/app/providers/google.py`
- Create: `v2/app/providers/registry.py`
- Create: `v2/tests/test_providers.py`

**Step 1: Write failing test**

```python
# tests/test_providers.py
import pytest
from app.providers.registry import resolve_provider


def test_resolve_anthropic_provider():
    provider = resolve_provider("claude-sonnet-4-20250514")
    assert provider.provider_name == "anthropic"


def test_resolve_openai_provider():
    provider = resolve_provider("gpt-4o")
    assert provider.provider_name == "openai"


def test_resolve_google_provider():
    provider = resolve_provider("gemini-2.5-flash")
    assert provider.provider_name == "google"


def test_resolve_unknown_model_raises():
    with pytest.raises(ValueError):
        resolve_provider("unknown-model-xyz")
```

**Step 2: Run test to verify it fails**

Run: `cd v2 && python -m pytest tests/test_providers.py -v`
Expected: FAIL

**Step 3: Implement provider layer**

`app/providers/base.py`:
```python
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
```

`app/providers/anthropic.py`:
```python
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
```

`app/providers/openai.py`:
```python
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
            text=response.choices[0].message.content,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
```

`app/providers/google.py`:
```python
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
```

`app/providers/registry.py`:
```python
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
```

`app/providers/__init__.py`:
```python
from app.providers.base import BaseProvider, GenerationResult
from app.providers.registry import resolve_provider

__all__ = ["BaseProvider", "GenerationResult", "resolve_provider"]
```

**Step 4: Run tests**

Run: `cd v2 && python -m pytest tests/test_providers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add v2/
git commit -m "feat(v2): AI provider layer with Anthropic, OpenAI, Google support"
```

---

### Task 7: Embedding Service

**Files:**
- Create: `v2/app/services/embeddings.py`
- Create: `v2/tests/test_embeddings.py`

**Step 1: Write the embedding service**

`app/services/embeddings.py`:
```python
from openai import AsyncOpenAI

from app.config import settings


async def generate_embedding(text: str, api_key: str | None = None) -> list[float]:
    client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)
    response = await client.embeddings.create(
        input=text,
        model=settings.embedding_model,
    )
    return response.data[0].embedding
```

**Step 2: Commit**

```bash
git add v2/
git commit -m "feat(v2): embedding service using OpenAI"
```

---

### Task 8: Template Endpoints (CRUD + Vector Search)

**Files:**
- Create: `v2/app/schemas/template.py`
- Create: `v2/app/routers/templates.py`
- Create: `v2/tests/test_templates.py`

**Step 1: Write failing tests**

```python
# tests/test_templates.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_template_crud():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/accounts", json={"name": "Test"})
        api_key = resp.json()["api_key"]
        headers = {"Authorization": f"Bearer {api_key}"}

        # Create template
        resp = await client.post("/templates", json={
            "content": "I spent [X years] [doing activity]...",
            "description": "Experience reflection template",
            "category": "short_form",
        }, headers=headers)
        assert resp.status_code == 201
        template_id = resp.json()["id"]

        # List
        resp = await client.get("/templates", headers=headers)
        assert resp.status_code == 200

        # Get
        resp = await client.get(f"/templates/{template_id}", headers=headers)
        assert resp.status_code == 200

        # Delete
        resp = await client.delete(f"/templates/{template_id}", headers=headers)
        assert resp.status_code == 204
```

**Step 2: Run test to verify it fails**

**Step 3: Create schemas**

`app/schemas/template.py`:
```python
import uuid
from datetime import datetime
from pydantic import BaseModel

from app.models.template import TemplateCategory


class TemplateCreate(BaseModel):
    content: str
    description: str = ""
    category: TemplateCategory = TemplateCategory.short_form


class TemplateResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    content: str
    description: str
    category: TemplateCategory
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateSearchRequest(BaseModel):
    query: str
    category: TemplateCategory | None = None
    limit: int = 5


class TemplateSearchResponse(BaseModel):
    templates: list[TemplateResponse]
```

**Step 4: Create router**

`app/routers/templates.py` — on create, auto-generates embedding. Search endpoint uses pgvector cosine distance.

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_account
from app.models.account import Account
from app.models.template import Template, TemplateCategory
from app.schemas.template import TemplateCreate, TemplateResponse, TemplateSearchRequest, TemplateSearchResponse
from app.services.embeddings import generate_embedding

router = APIRouter(tags=["templates"])


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    body: TemplateCreate,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    # Generate embedding from content + description
    embed_text = f"{body.content}\n{body.description}" if body.description else body.content
    embedding = await generate_embedding(embed_text)

    template = Template(
        account_id=account.id,
        content=body.content,
        description=body.description,
        category=body.category,
        embedding=embedding,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(
    category: TemplateCategory | None = None,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Template).where(
        or_(Template.account_id == account.id, Template.account_id.is_(None))
    )
    if category:
        stmt = stmt.where(Template.category == category)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    t = await db.get(Template, template_id)
    if not t or (t.account_id is not None and t.account_id != account.id):
        raise HTTPException(status_code=404, detail="Template not found")
    return t


@router.post("/templates/search", response_model=TemplateSearchResponse)
async def search_templates(
    body: TemplateSearchRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    query_embedding = await generate_embedding(body.query)
    stmt = (
        select(Template)
        .where(or_(Template.account_id == account.id, Template.account_id.is_(None)))
        .order_by(Template.embedding.cosine_distance(query_embedding))
        .limit(body.limit)
    )
    if body.category:
        stmt = stmt.where(Template.category == body.category)
    result = await db.execute(stmt)
    return TemplateSearchResponse(templates=list(result.scalars().all()))


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    t = await db.get(Template, template_id)
    if not t or t.account_id != account.id:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.delete(t)
    await db.commit()
```

**Step 5: Register router, run tests**

Expected: PASS

**Step 6: Commit**

```bash
git add v2/
git commit -m "feat(v2): template CRUD with vector search"
```

---

### Task 9: Source Content Endpoints (CRUD + Upload + Batch + Twitter + Search)

**Files:**
- Create: `v2/app/schemas/source_content.py`
- Create: `v2/app/routers/source_content.py`
- Create: `v2/app/services/documents.py`
- Create: `v2/app/services/twitter.py`
- Create: `v2/tests/test_source_content.py`

**Step 1: Write failing tests**

```python
# tests/test_source_content.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_source_content_crud():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/accounts", json={"name": "Test"})
        api_key = resp.json()["api_key"]
        headers = {"Authorization": f"Bearer {api_key}"}

        # Create direct source content
        resp = await client.post("/source-content", json={
            "content": "AI is transforming business operations.",
            "source": "manual",
        }, headers=headers)
        assert resp.status_code == 201

        # Batch import
        resp = await client.post("/source-content/batch", json={
            "items": [
                {"content": "First item", "source": "blog"},
                {"content": "Second item", "source": "newsletter", "metadata": {"score": 10}},
            ]
        }, headers=headers)
        assert resp.status_code == 201
        assert len(resp.json()) == 2

        # List
        resp = await client.get("/source-content", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 3
```

**Step 2: Run test to verify it fails**

**Step 3: Create schemas**

`app/schemas/source_content.py`:
```python
import uuid
from datetime import datetime
from pydantic import BaseModel


class SourceContentCreate(BaseModel):
    content: str
    source: str = "manual"
    channel_source: str = "manual"
    metadata: dict | None = None


class SourceContentBatchItem(BaseModel):
    content: str
    source: str = "manual"
    channel_source: str = "manual"
    metadata: dict | None = None


class SourceContentBatchRequest(BaseModel):
    items: list[SourceContentBatchItem]


class SourceContentResponse(BaseModel):
    id: uuid.UUID
    content: str
    source: str
    channel_source: str
    metadata: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceContentSearchRequest(BaseModel):
    query: str
    limit: int = 5


class SourceContentSearchResponse(BaseModel):
    results: list[SourceContentResponse]


class TwitterImportRequest(BaseModel):
    profile_url: str
    max_tweets: int = 50


class TwitterImportResponse(BaseModel):
    imported_count: int
    items: list[SourceContentResponse]
```

**Step 4: Create document processing service**

`app/services/documents.py`:
```python
import io

import fitz  # PyMuPDF
import docx
import markdown


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    extractors = {
        "pdf": _extract_pdf,
        "docx": _extract_docx,
        "md": _extract_markdown,
        "txt": _extract_text,
    }
    extractor = extractors.get(ext)
    if not extractor:
        raise ValueError(f"Unsupported file type: {ext}")
    return extractor(file_bytes)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            while end < len(text) and text[end] != " ":
                end += 1
        chunks.append(text[start:end].strip())
        start = end - overlap
        if start > 0:
            while start < len(text) and text[start] != " ":
                start += 1
    return [c for c in chunks if c]


def _extract_pdf(data: bytes) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    return "".join(page.get_text() for page in doc)


def _extract_docx(data: bytes) -> str:
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def _extract_markdown(data: bytes) -> str:
    html = markdown.markdown(data.decode("utf-8"))
    return html.replace("<p>", "").replace("</p>", "\n")


def _extract_text(data: bytes) -> str:
    return data.decode("utf-8")
```

**Step 5: Create Twitter import service**

`app/services/twitter.py` — extracted from V1's `source_content_manager.py`, cleaned up:
```python
import httpx

from app.config import settings


async def fetch_tweets(profile_url: str, max_tweets: int = 50) -> list[dict]:
    handle = profile_url.rstrip("/").split("/")[-1].lstrip("@")

    async with httpx.AsyncClient(timeout=120) as client:
        # Start Apify actor
        resp = await client.post(
            "https://api.apify.com/v2/acts/apidojo~tweet-scraper/runs",
            params={"token": settings.apify_api_token},
            json={
                "handles": [handle],
                "tweetsDesired": max_tweets,
                "proxyConfig": {"useApifyProxy": True},
            },
        )
        resp.raise_for_status()
        run_id = resp.json()["data"]["id"]

        # Wait for completion
        resp = await client.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items",
            params={"token": settings.apify_api_token},
        )
        resp.raise_for_status()
        return resp.json()


def score_tweet(tweet: dict, follower_count: int) -> dict:
    likes = tweet.get("likeCount", 0)
    replies = tweet.get("replyCount", 0)
    retweets = tweet.get("retweetCount", 0)
    bookmarks = tweet.get("bookmarkCount", 0)
    impressions = tweet.get("viewCount", 0) or 1

    impression_ratio = impressions / max(follower_count, 1)

    return {
        "weighted_impressions": (impression_ratio) * 0.15,
        "weighted_replies": (replies / impression_ratio) * 0.25 if impression_ratio else 0,
        "weighted_bookmarks": (bookmarks / impression_ratio) * 0.25 if impression_ratio else 0,
        "weighted_retweets": (retweets / impression_ratio) * 0.15 if impression_ratio else 0,
        "weighted_likes": (likes / impression_ratio) * 0.20 if impression_ratio else 0,
        "likes": likes,
        "replies": replies,
        "retweets": retweets,
        "bookmarks": bookmarks,
        "impressions": impressions,
    }
```

**Step 6: Create source content router**

`app/routers/source_content.py` — handles direct create, batch, file upload, Twitter import, vector search, list, delete.

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_account
from app.models.account import Account
from app.models.source_content import SourceContent
from app.schemas.source_content import (
    SourceContentCreate, SourceContentResponse,
    SourceContentBatchRequest,
    SourceContentSearchRequest, SourceContentSearchResponse,
    TwitterImportRequest, TwitterImportResponse,
)
from app.services.embeddings import generate_embedding
from app.services.documents import extract_text, chunk_text
from app.services.twitter import fetch_tweets, score_tweet

router = APIRouter(prefix="/source-content", tags=["source-content"])


@router.post("", response_model=SourceContentResponse, status_code=201)
async def create_source_content(
    body: SourceContentCreate,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    embedding = await generate_embedding(body.content)
    sc = SourceContent(
        account_id=account.id,
        content=body.content,
        source=body.source,
        channel_source=body.channel_source,
        embedding=embedding,
        metadata_=body.metadata,
    )
    db.add(sc)
    await db.commit()
    await db.refresh(sc)
    return sc


@router.post("/batch", response_model=list[SourceContentResponse], status_code=201)
async def batch_import(
    body: SourceContentBatchRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    results = []
    for item in body.items:
        embedding = await generate_embedding(item.content)
        sc = SourceContent(
            account_id=account.id,
            content=item.content,
            source=item.source,
            channel_source=item.channel_source,
            embedding=embedding,
            metadata_=item.metadata,
        )
        db.add(sc)
        results.append(sc)
    await db.commit()
    for sc in results:
        await db.refresh(sc)
    return results


@router.post("/upload", response_model=list[SourceContentResponse], status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    file_bytes = await file.read()
    text = extract_text(file_bytes, file.filename)
    chunks = chunk_text(text)

    results = []
    for chunk in chunks:
        embedding = await generate_embedding(chunk)
        sc = SourceContent(
            account_id=account.id,
            content=chunk,
            source=file.filename,
            channel_source=file.filename.rsplit(".", 1)[-1].upper(),
            embedding=embedding,
        )
        db.add(sc)
        results.append(sc)
    await db.commit()
    for sc in results:
        await db.refresh(sc)
    return results


@router.post("/import-twitter", response_model=TwitterImportResponse, status_code=201)
async def import_twitter(
    body: TwitterImportRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    tweets = await fetch_tweets(body.profile_url, body.max_tweets)
    follower_count = tweets[0].get("author", {}).get("followers", 1) if tweets else 1

    results = []
    for tweet in tweets:
        if tweet.get("isRetweet"):
            continue
        text = tweet.get("fullText") or tweet.get("text", "")
        if not text:
            continue

        metrics = score_tweet(tweet, follower_count)
        metrics["total_weight_metric"] = sum(
            v for k, v in metrics.items() if k.startswith("weighted_")
        )

        embedding = await generate_embedding(text)
        sc = SourceContent(
            account_id=account.id,
            content=text,
            source="Twitter",
            channel_source="Twitter",
            embedding=embedding,
            metadata_=metrics,
        )
        db.add(sc)
        results.append(sc)

    await db.commit()
    for sc in results:
        await db.refresh(sc)
    return TwitterImportResponse(imported_count=len(results), items=results)


@router.get("", response_model=list[SourceContentResponse])
async def list_source_content(
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SourceContent).where(SourceContent.account_id == account.id)
    )
    return result.scalars().all()


@router.post("/search", response_model=SourceContentSearchResponse)
async def search_source_content(
    body: SourceContentSearchRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    query_embedding = await generate_embedding(body.query)
    stmt = (
        select(SourceContent)
        .where(SourceContent.account_id == account.id)
        .order_by(SourceContent.embedding.cosine_distance(query_embedding))
        .limit(body.limit)
    )
    result = await db.execute(stmt)
    return SourceContentSearchResponse(results=list(result.scalars().all()))


@router.delete("/{content_id}", status_code=204)
async def delete_source_content(
    content_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    sc = await db.get(SourceContent, content_id)
    if not sc or sc.account_id != account.id:
        raise HTTPException(status_code=404, detail="Source content not found")
    await db.delete(sc)
    await db.commit()
```

**Step 7: Register router, run tests**

Expected: PASS

**Step 8: Commit**

```bash
git add v2/
git commit -m "feat(v2): source content endpoints with file upload, batch import, Twitter, and vector search"
```

---

### Task 10: Workflow Engine & Generate Endpoint

**Files:**
- Create: `v2/app/engine/__init__.py`
- Create: `v2/app/engine/executor.py`
- Create: `v2/app/schemas/generation.py`
- Create: `v2/app/routers/generation.py`
- Create: `v2/tests/test_engine.py`

**Step 1: Write failing test for variable substitution**

```python
# tests/test_engine.py
import pytest
from app.engine.executor import substitute_variables


def test_substitute_variables():
    template = "Content: {content}\nTemplate: {template}\nVoice: {brand_voice}"
    context = {
        "content": "AI is great",
        "template": "Use a hook",
        "brand_voice": "Casual tone",
        "prev_ai_output": "",
    }
    result = substitute_variables(template, context)
    assert "AI is great" in result
    assert "Use a hook" in result
    assert "Casual tone" in result


def test_substitute_with_prev_output():
    template = "Refine this: {prev_ai_output}"
    context = {
        "content": "",
        "template": "",
        "brand_voice": "",
        "prev_ai_output": "Draft text here",
    }
    result = substitute_variables(template, context)
    assert "Draft text here" in result
```

**Step 2: Run test to verify it fails**

**Step 3: Implement the engine**

`app/engine/executor.py`:
```python
from app.providers import resolve_provider, GenerationResult


def substitute_variables(template: str, context: dict) -> str:
    result = template
    for key, value in context.items():
        result = result.replace(f"{{{key}}}", value or "")
    return result


async def execute_workflow(
    steps: list[dict],
    context: dict,
    provider_keys: dict | None = None,
) -> list[dict]:
    """
    Execute workflow steps sequentially.
    Returns list of step results with token usage.
    """
    prev_output = ""
    step_results = []

    for step in sorted(steps, key=lambda s: s["order"]):
        context["prev_ai_output"] = prev_output

        user_prompt = substitute_variables(step["user_prompt"], context)
        system_prompt = substitute_variables(step["system_prompt"], context)

        provider = resolve_provider(step["model"])

        # Resolve API key: request-level override → system fallback
        api_key = None
        if provider_keys:
            api_key = provider_keys.get(provider.provider_name)

        result: GenerationResult = await provider.generate(
            model=step["model"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=step.get("max_tokens", 4096),
            temperature=step.get("temperature", 0.7),
            api_key=api_key,
        )

        prev_output = result.text
        step_results.append({
            "step": step["order"],
            "name": step["name"],
            "model": step["model"],
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        })

    return step_results, prev_output
```

`app/engine/__init__.py`:
```python
from app.engine.executor import execute_workflow, substitute_variables

__all__ = ["execute_workflow", "substitute_variables"]
```

**Step 4: Run engine tests**

Run: `cd v2 && python -m pytest tests/test_engine.py -v`
Expected: PASS

**Step 5: Create generation schemas**

`app/schemas/generation.py`:
```python
import uuid
from pydantic import BaseModel


class ProviderKeys(BaseModel):
    anthropic: str | None = None
    openai: str | None = None
    google: str | None = None


class GenerateRequest(BaseModel):
    workflow_id: uuid.UUID

    # Content input
    content: str | None = None
    content_query: str | None = None

    # Template input
    template: str | None = None
    template_query: str | None = None
    template_count: int = 1

    # Context
    brand_id: uuid.UUID | None = None

    # Provider keys
    provider_keys: ProviderKeys | None = None


class StepUsage(BaseModel):
    step: int
    name: str
    model: str
    input_tokens: int
    output_tokens: int


class GenerationItem(BaseModel):
    id: uuid.UUID
    output: str
    template_used: str | None
    token_usage: dict


class GenerateResponse(BaseModel):
    generations: list[GenerationItem]
```

**Step 6: Create generation router**

`app/routers/generation.py`:
```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_account
from app.models.account import Account
from app.models.workflow import Workflow
from app.models.brand_voice import BrandVoice
from app.models.template import Template
from app.models.source_content import SourceContent
from app.models.generated_content import GeneratedContent
from app.schemas.generation import GenerateRequest, GenerateResponse, GenerationItem
from app.engine import execute_workflow
from app.services.embeddings import generate_embedding

router = APIRouter(tags=["generation"])


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: GenerateRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    # 1. Load workflow
    wf = await db.get(Workflow, body.workflow_id)
    if not wf or (wf.account_id is not None and wf.account_id != account.id):
        raise HTTPException(status_code=404, detail="Workflow not found")

    # 2. Resolve content
    content = body.content or ""
    if body.content_query:
        query_emb = await generate_embedding(body.content_query)
        stmt = (
            select(SourceContent)
            .where(SourceContent.account_id == account.id)
            .order_by(SourceContent.embedding.cosine_distance(query_emb))
            .limit(3)
        )
        result = await db.execute(stmt)
        matches = result.scalars().all()
        content = "\n\n".join(m.content for m in matches)

    # 3. Resolve brand voice
    brand_voice = ""
    if body.brand_id:
        brand = await db.get(BrandVoice, body.brand_id)
        if not brand or brand.account_id != account.id:
            raise HTTPException(status_code=404, detail="Brand not found")
        brand_voice = brand.voice_guidelines

    # 4. Resolve templates
    templates_to_use: list[str | None] = []
    if body.template:
        templates_to_use = [body.template]
    elif body.template_query:
        query_emb = await generate_embedding(body.template_query)
        stmt = (
            select(Template)
            .where(or_(Template.account_id == account.id, Template.account_id.is_(None)))
            .order_by(Template.embedding.cosine_distance(query_emb))
            .limit(body.template_count)
        )
        result = await db.execute(stmt)
        templates_to_use = [t.content for t in result.scalars().all()]
    else:
        templates_to_use = [None]

    # Ensure we have at least one template slot
    if not templates_to_use:
        templates_to_use = [None]

    # 5. Build provider keys dict
    provider_keys = None
    if body.provider_keys:
        provider_keys = body.provider_keys.model_dump(exclude_none=True)

    # 6. Execute for each template
    generations = []
    for tmpl in templates_to_use:
        context = {
            "content": content,
            "template": tmpl or "",
            "brand_voice": brand_voice,
            "prev_ai_output": "",
        }

        step_results, final_output = await execute_workflow(
            steps=wf.steps,
            context=context,
            provider_keys=provider_keys,
        )

        total_tokens = sum(s["input_tokens"] + s["output_tokens"] for s in step_results)

        # Record to DB
        gc = GeneratedContent(
            account_id=account.id,
            workflow_id=wf.id,
            brand_id=body.brand_id,
            input_content=content,
            input_template=tmpl,
            output=final_output,
            token_usage={"steps": step_results, "total_tokens": total_tokens},
        )
        db.add(gc)
        await db.flush()

        generations.append(GenerationItem(
            id=gc.id,
            output=final_output,
            template_used=tmpl,
            token_usage={"steps": step_results, "total_tokens": total_tokens},
        ))

    await db.commit()
    return GenerateResponse(generations=generations)
```

**Step 7: Create generated content read-only router**

Add to `app/routers/generation.py`:
```python
from app.schemas.source_content import SourceContentResponse  # reuse pattern


class GeneratedContentResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    brand_id: uuid.UUID | None
    input_content: str
    input_template: str | None
    output: str
    token_usage: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/generated-content", response_model=list[GeneratedContentResponse])
async def list_generated_content(
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GeneratedContent)
        .where(GeneratedContent.account_id == account.id)
        .order_by(GeneratedContent.created_at.desc())
    )
    return result.scalars().all()


@router.get("/generated-content/{content_id}", response_model=GeneratedContentResponse)
async def get_generated_content(
    content_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    gc = await db.get(GeneratedContent, content_id)
    if not gc or gc.account_id != account.id:
        raise HTTPException(status_code=404, detail="Generated content not found")
    return gc
```

Add `from datetime import datetime` and `from pydantic import BaseModel` to the imports at the top.

**Step 8: Register router, run tests**

Run: `cd v2 && python -m pytest tests/ -v`
Expected: PASS

**Step 9: Commit**

```bash
git add v2/
git commit -m "feat(v2): workflow engine and /generate endpoint"
```

---

### Task 11: Templatize Endpoint

**Files:**
- Create: `v2/app/routers/templatize.py`
- Create: `v2/tests/test_templatize.py`

**Step 1: Write failing test**

```python
# tests/test_templatize.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_templatize_returns_template():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/accounts", json={"name": "Test"})
        api_key = resp.json()["api_key"]
        headers = {"Authorization": f"Bearer {api_key}"}

        resp = await client.post("/templatize", json={
            "content": "I spent 10 years building software and here is the truth..."
        }, headers=headers)
        assert resp.status_code == 200
        assert "template" in resp.json()
```

**Step 2: Create router**

`app/routers/templatize.py`:
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_account
from app.models.account import Account
from app.providers import resolve_provider
from app.config import settings

router = APIRouter(tags=["templatize"])

TEMPLATIZER_SYSTEM_PROMPT = """Create a versatile social media post template by analyzing the content and extracting its structural patterns, emotional hooks, and rhetorical devices while removing the specific subject matter.

Steps:
1. Analyze the post's structure, formatting, and stylistic elements
2. Identify key components that make it engaging
3. Strip away specific content while preserving the structural framework
4. Mark variable elements with clear [placeholder] notation

Output only the template, nothing else."""


class TemplatizeRequest(BaseModel):
    content: str
    model: str = "claude-haiku-4-5-20251001"
    provider_key: str | None = None


class TemplatizeResponse(BaseModel):
    template: str


@router.post("/templatize", response_model=TemplatizeResponse)
async def templatize(
    body: TemplatizeRequest,
    account: Account = Depends(get_current_account),
):
    provider = resolve_provider(body.model)
    result = await provider.generate(
        model=body.model,
        system_prompt=TEMPLATIZER_SYSTEM_PROMPT,
        user_prompt=body.content,
        max_tokens=2048,
        temperature=0.7,
        api_key=body.provider_key,
    )
    return TemplatizeResponse(template=result.text)
```

**Step 3: Register router, run tests**

Expected: PASS (with mocked provider in integration tests)

**Step 4: Commit**

```bash
git add v2/
git commit -m "feat(v2): templatize endpoint"
```

---

### Task 12: Wire All Routers & Final main.py

**Files:**
- Modify: `v2/app/main.py`

**Step 1: Update main.py to include all routers**

```python
from fastapi import FastAPI

from app.routers import accounts, brands, workflows, templates, source_content, generation, templatize

app = FastAPI(title="Ghostwriter V2", version="2.0.0")

app.include_router(accounts.router)
app.include_router(brands.router)
app.include_router(workflows.router)
app.include_router(templates.router)
app.include_router(source_content.router)
app.include_router(generation.router)
app.include_router(templatize.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 2: Run full test suite**

Run: `cd v2 && python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add v2/
git commit -m "feat(v2): wire all routers into main app"
```

---

### Task 13: Test Database Fixture Setup

**Files:**
- Create: `v2/tests/conftest.py`

**Step 1: Create test fixtures**

Tests need a real test database (or in-memory). Set up conftest.py with test database session override:

```python
import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base, get_db
from app.main import app
from app.config import settings

TEST_DATABASE_URL = settings.database_url.replace("/ghostwriter", "/ghostwriter_test")

test_engine = create_async_engine(TEST_DATABASE_URL)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
```

**Step 2: Run full test suite with fixtures**

Run: `cd v2 && python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add v2/
git commit -m "feat(v2): test database fixtures"
```

---

### Task 14: Docker Compose Verification & Smoke Test

**Step 1: Bring up full stack**

```bash
cd v2 && docker compose up --build -d
```

**Step 2: Run migrations**

```bash
docker compose exec api alembic upgrade head
```

**Step 3: Smoke test**

```bash
# Health check
curl http://localhost:8000/health

# Create account
curl -X POST http://localhost:8000/accounts -H "Content-Type: application/json" -d '{"name":"smoke-test"}'

# Use returned API key for subsequent requests
# Create a brand, create a workflow, test /generate
```

**Step 4: Verify OpenAPI docs are generated**

```bash
curl http://localhost:8000/openapi.json | python -m json.tool | head -50
```

Expected: Full OpenAPI spec with all endpoints documented.

**Step 5: Commit**

```bash
git add v2/
git commit -m "chore(v2): verified Docker Compose and smoke test"
```

---

## Summary

| Task | What it builds | Key files |
|------|---------------|-----------|
| 1 | Scaffolding + Docker | Dockerfile, docker-compose.yml, main.py, config.py |
| 2 | Database models + migrations | models/*.py, alembic/ |
| 3 | API key auth | auth/, routers/accounts.py |
| 4 | Brand voice CRUD | routers/brands.py |
| 5 | Workflow CRUD | routers/workflows.py |
| 6 | AI provider layer | providers/ (Anthropic, OpenAI, Google) |
| 7 | Embedding service | services/embeddings.py |
| 8 | Template CRUD + vector search | routers/templates.py |
| 9 | Source content (CRUD, upload, batch, Twitter, search) | routers/source_content.py, services/ |
| 10 | Workflow engine + /generate | engine/executor.py, routers/generation.py |
| 11 | Templatize endpoint | routers/templatize.py |
| 12 | Wire all routers | main.py |
| 13 | Test fixtures | tests/conftest.py |
| 14 | Docker verification + smoke test | — |
