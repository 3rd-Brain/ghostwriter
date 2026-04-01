import hashlib
import math

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.auth.service import get_or_create_default_account
from app.auth import get_current_account
from app.models.account import Account
from app.models.brand_voice import BrandVoice
from app.models.workflow import Workflow
from app.models.template import Template
from app.models.source_content import SourceContent
from app.models.generated_content import GeneratedContent, ContentStatus

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/ui", tags=["ui"], include_in_schema=False)

COOKIE_NAME = "gw_session"
COOKIE_MAX_AGE = 86400  # 24 hours


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def get_ui_account(request: Request, db: AsyncSession = Depends(get_db)) -> Account | None:
    """Authenticate UI requests via session cookie or skip if no auth needed."""
    if not settings.self_host_api_key and not settings.auth_enabled:
        return await get_or_create_default_account(db)

    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None

    if settings.self_host_api_key:
        if cookie == _hash_key(settings.self_host_api_key):
            return await get_or_create_default_account(db)
    return None


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if not settings.self_host_api_key and not settings.auth_enabled:
        return RedirectResponse("/ui", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, api_key: str = Form(...)):
    if settings.self_host_api_key and api_key == settings.self_host_api_key:
        response = RedirectResponse("/ui", status_code=302)
        response.set_cookie(
            COOKIE_NAME,
            _hash_key(api_key),
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid API key"})


@router.get("/logout")
async def logout():
    response = RedirectResponse("/ui/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    account: Account | None = Depends(get_ui_account),
    db: AsyncSession = Depends(get_db),
):
    if account is None:
        return RedirectResponse("/ui/login", status_code=302)
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
    account: Account | None = Depends(get_ui_account),
    db: AsyncSession = Depends(get_db),
):
    if account is None:
        return RedirectResponse("/ui/login", status_code=302)
    if status is None:
        return RedirectResponse("/ui/generations?status=new", status_code=302)

    stmt = (
        select(GeneratedContent)
        .where(GeneratedContent.account_id == account.id)
        .order_by(GeneratedContent.created_at.desc())
        .limit(100)
    )
    if status != "all":
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
    bp: int = 1,
    tp: int = 1,
    sp: int = 1,
    tc: str | None = None,
    account: Account | None = Depends(get_ui_account),
    db: AsyncSession = Depends(get_db),
):
    if account is None:
        return RedirectResponse("/ui/login", status_code=302)
    aid = account.id
    per_page = 10

    # Brands
    brand_total = (await db.execute(select(func.count()).select_from(BrandVoice).where(BrandVoice.account_id == aid))).scalar()
    brands = (await db.execute(
        select(BrandVoice).where(BrandVoice.account_id == aid)
        .order_by(BrandVoice.created_at.desc())
        .limit(per_page).offset((bp - 1) * per_page)
    )).scalars().all()

    # Templates — optional category filter
    tmpl_filter = or_(Template.account_id == aid, Template.account_id.is_(None))
    active_category = None
    if tc and tc in ("short_form", "atomic", "mid_form"):
        from app.models.template import TemplateCategory
        active_category = tc
        tmpl_filter = tmpl_filter & (Template.category == TemplateCategory(tc))
    tmpl_total = (await db.execute(select(func.count()).select_from(Template).where(tmpl_filter))).scalar()
    tmpl = (await db.execute(
        select(Template).where(tmpl_filter)
        .order_by(Template.created_at.desc())
        .limit(per_page).offset((tp - 1) * per_page)
    )).scalars().all()

    # Source Content
    sc_total = (await db.execute(select(func.count()).select_from(SourceContent).where(SourceContent.account_id == aid))).scalar()
    sc = (await db.execute(
        select(SourceContent).where(SourceContent.account_id == aid)
        .order_by(SourceContent.created_at.desc())
        .limit(per_page).offset((sp - 1) * per_page)
    )).scalars().all()

    return templates.TemplateResponse("library.html", {
        "request": request,
        "active_page": "library",
        "brands": brands,
        "brand_total": brand_total,
        "brand_pages": math.ceil(brand_total / per_page),
        "bp": bp,
        "templates": tmpl,
        "tmpl_total": tmpl_total,
        "tmpl_pages": math.ceil(tmpl_total / per_page),
        "tp": tp,
        "tc": active_category,
        "source_content": sc,
        "sc_total": sc_total,
        "sc_pages": math.ceil(sc_total / per_page),
        "sp": sp,
    })


@router.get("/workflows", response_class=HTMLResponse)
async def workflows_page(
    request: Request,
    account: Account | None = Depends(get_ui_account),
    db: AsyncSession = Depends(get_db),
):
    if account is None:
        return RedirectResponse("/ui/login", status_code=302)
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
