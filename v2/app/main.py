from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi_mcp import FastApiMCP, AuthConfig
from sqlalchemy import text

from app.config import settings
from app.database import async_session
from app.auth.service import get_or_create_default_account
from app.auth import get_current_account
from app.routers import accounts, brands, workflows, templates, source_content, generation, templatize
from app.routers import ui


def use_route_names_as_operation_ids(route: APIRoute) -> str:
    return route.name


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables on startup (dev convenience — use Alembic in production)
    from app.database import engine, Base
    import app.models.account, app.models.brand_voice, app.models.workflow
    import app.models.template, app.models.source_content, app.models.generated_content
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    if not settings.auth_enabled:
        async with async_session() as db:
            await get_or_create_default_account(db)
    yield


app = FastAPI(
    title="Ghostwriter",
    version="2.0.0",
    description="AI content generation API. Ingest source content, define brand voices and templates, then generate social posts using multi-step LLM workflows.",
    lifespan=lifespan,
    generate_unique_id_function=use_route_names_as_operation_ids,
)

app.include_router(accounts.router)
app.include_router(brands.router)
app.include_router(workflows.router)
app.include_router(templates.router)
app.include_router(source_content.router)
app.include_router(generation.router)
app.include_router(templatize.router)
app.include_router(ui.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health", summary="Health check", description="Returns API health status.")
async def health():
    return {"status": "ok"}


# MCP server — exposes all endpoints as MCP tools for AI agent consumption
mcp = FastApiMCP(
    app,
    name="Ghostwriter MCP",
    description="AI content generation tools. Manage brands, workflows, templates, source content, and generate social posts via multi-step LLM workflows.",
    exclude_operations=["upload_file", "health"],
    auth_config=AuthConfig(
        dependencies=[Depends(get_current_account)],
    ) if (settings.auth_enabled or settings.self_host_api_key) else None,
)
mcp.mount_http()
