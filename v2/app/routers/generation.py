import uuid
from datetime import datetime

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
from app.schemas.generation import GenerateRequest, GenerateResponse, GenerationItem, GeneratedContentResponse
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
