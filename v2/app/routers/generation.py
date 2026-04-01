import asyncio
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session as _default_session_factory
from app.auth import get_current_account
from app.models.account import Account
from app.models.workflow import Workflow
from app.models.brand_voice import BrandVoice
from app.models.template import Template
from app.models.source_content import SourceContent
from app.models.generated_content import GeneratedContent
from app.models.generated_content import ContentStatus
from app.schemas.generation import GenerateRequest, GenerateStartedResponse, GeneratedContentResponse, UpdateStatusRequest
from app.engine import execute_workflow
from app.services.embeddings import generate_embedding

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])

# Session factory used by background tasks. Tests can patch this to inject
# a test-scoped session factory (since background tasks don't go through
# FastAPI's Depends(get_db) override).
session_factory = _default_session_factory


async def _run_generation_background(
    account_id: uuid.UUID,
    workflow_steps: list[dict],
    workflow_id: uuid.UUID,
    brand_id: uuid.UUID | None,
    content: str,
    brand_voice: str,
    templates: list[str | None],
    provider_keys: dict | None,
):
    """Run content generation in the background. Each piece of content is
    committed to the DB as it completes so it appears in the UI immediately."""
    for tmpl in templates:
        try:
            context = {
                "content": content,
                "template": tmpl or "",
                "brand_voice": brand_voice,
                "prev_ai_output": "",
            }

            step_results, final_output = await execute_workflow(
                steps=workflow_steps,
                context=context,
                provider_keys=provider_keys,
            )

            total_tokens = sum(s["input_tokens"] + s["output_tokens"] for s in step_results)

            async with session_factory() as db:
                gc = GeneratedContent(
                    account_id=account_id,
                    workflow_id=workflow_id,
                    brand_id=brand_id,
                    input_content=content,
                    input_template=tmpl,
                    output=final_output,
                    token_usage={"steps": step_results, "total_tokens": total_tokens},
                )
                db.add(gc)
                await db.commit()

            logger.info("Generation completed for template (workflow=%s)", workflow_id)

        except Exception:
            logger.exception(
                "Background generation failed for template (workflow=%s)",
                workflow_id,
            )


@router.post("/generate", response_model=GenerateStartedResponse, summary="Generate content", description="Fire-and-forget: validates inputs, starts generation in the background, and returns immediately. Generated content appears in the UI as each piece completes.")
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

    if not templates_to_use:
        templates_to_use = [None]

    # 5. Build provider keys dict
    provider_keys = None
    if body.provider_keys:
        provider_keys = body.provider_keys.model_dump(exclude_none=True)

    # Snapshot workflow steps so the background task doesn't depend on
    # the request-scoped DB session (which closes after response).
    workflow_steps = list(wf.steps)

    # 6. Fire off generation in the background — returns immediately
    asyncio.create_task(
        _run_generation_background(
            account_id=account.id,
            workflow_steps=workflow_steps,
            workflow_id=wf.id,
            brand_id=body.brand_id,
            content=content,
            brand_voice=brand_voice,
            templates=templates_to_use,
            provider_keys=provider_keys,
        )
    )

    return GenerateStartedResponse(
        status="started",
        message="Generation started. Content will appear in your dashboard as it completes.",
        template_count=len(templates_to_use),
    )


@router.get("/generated-content", response_model=list[GeneratedContentResponse], summary="List generated content", description="List previously generated content with pagination.")
async def list_generated_content(
    limit: int = 50,
    offset: int = 0,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GeneratedContent)
        .where(GeneratedContent.account_id == account.id)
        .order_by(GeneratedContent.created_at.desc())
        .limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.get("/generated-content/{content_id}", response_model=GeneratedContentResponse, summary="Get generated content", description="Get a specific generated content item by ID.")
async def get_generated_content(
    content_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    gc = await db.get(GeneratedContent, content_id)
    if not gc or gc.account_id != account.id:
        raise HTTPException(status_code=404, detail="Generated content not found")
    return gc


@router.patch("/generated-content/{content_id}/status", response_model=GeneratedContentResponse, summary="Update content status", description="Update the review status of generated content (new, approved, disapproved, posted).")
async def update_content_status(
    content_id: uuid.UUID,
    body: UpdateStatusRequest,
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    gc = await db.get(GeneratedContent, content_id)
    if not gc or gc.account_id != account.id:
        raise HTTPException(status_code=404, detail="Generated content not found")
    gc.status = ContentStatus(body.status)
    await db.commit()
    await db.refresh(gc)

    # Return HTML fragment for htmx, JSON for API clients
    if request.headers.get("HX-Request"):
        badge_html = f'<span class="status-badge status-{gc.status.value}" id="badge-{gc.id}">{gc.status.value}</span>'
        return HTMLResponse(badge_html)
    return gc
