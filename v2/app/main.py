from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import async_session
from app.auth.service import get_or_create_default_account
from app.routers import brands, workflows, templates, source_content, generation, templatize


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.auth_enabled:
        async with async_session() as db:
            await get_or_create_default_account(db)
    yield


app = FastAPI(
    title="Ghostwriter",
    version="2.0.0",
    description="AI content generation API. Ingest source content, define brand voices and templates, then generate social posts using multi-step LLM workflows.",
    lifespan=lifespan,
)

from app.routers import accounts
app.include_router(accounts.router)
app.include_router(brands.router)
app.include_router(workflows.router)
app.include_router(templates.router)
app.include_router(source_content.router)
app.include_router(generation.router)
app.include_router(templatize.router)


@app.get("/health", summary="Health check", description="Returns API health status.")
async def health():
    return {"status": "ok"}
