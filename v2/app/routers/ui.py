from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_account
from app.models.account import Account
from app.models.brand_voice import BrandVoice
from app.models.workflow import Workflow
from app.models.template import Template
from app.models.source_content import SourceContent
from app.models.generated_content import GeneratedContent, ContentStatus

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/ui", tags=["ui"], include_in_schema=False)


@router.get("", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    aid = account.id

    gen_count = (await db.execute(select(func.count()).select_from(GeneratedContent).where(GeneratedContent.account_id == aid))).scalar()
    pending = (await db.execute(select(func.count()).select_from(GeneratedContent).where(GeneratedContent.account_id == aid, GeneratedContent.status == ContentStatus.new))).scalar()
    approved = (await db.execute(select(func.count()).select_from(GeneratedContent).where(GeneratedContent.account_id == aid, GeneratedContent.status == ContentStatus.approved))).scalar()
    posted = (await db.execute(select(func.count()).select_from(GeneratedContent).where(GeneratedContent.account_id == aid, GeneratedContent.status == ContentStatus.posted))).scalar()
    brands = (await db.execute(select(func.count()).select_from(BrandVoice).where(BrandVoice.account_id == aid))).scalar()
    workflows = (await db.execute(select(func.count()).select_from(Workflow).where(or_(Workflow.account_id == aid, Workflow.account_id.is_(None))))).scalar()
    tmpl_count = (await db.execute(select(func.count()).select_from(Template).where(or_(Template.account_id == aid, Template.account_id.is_(None))))).scalar()
    sc_count = (await db.execute(select(func.count()).select_from(SourceContent).where(SourceContent.account_id == aid))).scalar()

    recent_result = await db.execute(
        select(GeneratedContent)
        .where(GeneratedContent.account_id == aid)
        .order_by(GeneratedContent.created_at.desc())
        .limit(5)
    )
    recent = recent_result.scalars().all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "stats": {
            "generations": gen_count,
            "pending": pending,
            "approved": approved,
            "posted": posted,
            "brands": brands,
            "workflows": workflows,
            "templates": tmpl_count,
            "source_content": sc_count,
        },
        "recent": recent,
    })


@router.get("/generations", response_class=HTMLResponse)
async def generations_page(
    request: Request,
    status: str | None = None,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(GeneratedContent)
        .where(GeneratedContent.account_id == account.id)
        .order_by(GeneratedContent.created_at.desc())
        .limit(100)
    )
    if status:
        stmt = stmt.where(GeneratedContent.status == ContentStatus(status))

    result = await db.execute(stmt)
    items = result.scalars().all()

    return templates.TemplateResponse("generations.html", {
        "request": request,
        "active_page": "generations",
        "items": items,
        "status_filter": status,
    })


@router.get("/library", response_class=HTMLResponse)
async def library_page(
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    aid = account.id

    brands = (await db.execute(select(BrandVoice).where(BrandVoice.account_id == aid).order_by(BrandVoice.created_at.desc()))).scalars().all()
    tmpl = (await db.execute(select(Template).where(or_(Template.account_id == aid, Template.account_id.is_(None))).order_by(Template.created_at.desc()).limit(100))).scalars().all()
    sc = (await db.execute(select(SourceContent).where(SourceContent.account_id == aid).order_by(SourceContent.created_at.desc()).limit(100))).scalars().all()

    return templates.TemplateResponse("library.html", {
        "request": request,
        "active_page": "library",
        "brands": brands,
        "templates": tmpl,
        "source_content": sc,
    })


@router.get("/workflows", response_class=HTMLResponse)
async def workflows_page(
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow)
        .where(or_(Workflow.account_id == account.id, Workflow.account_id.is_(None)))
        .order_by(Workflow.created_at.desc())
    )
    workflows = result.scalars().all()

    return templates.TemplateResponse("workflows.html", {
        "request": request,
        "active_page": "workflows",
        "workflows": workflows,
    })
