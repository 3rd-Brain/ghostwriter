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
    limit: int = 50,
    offset: int = 0,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Template).where(
        or_(Template.account_id == account.id, Template.account_id.is_(None))
    )
    if category:
        stmt = stmt.where(Template.category == category)
    stmt = stmt.limit(limit).offset(offset)
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
