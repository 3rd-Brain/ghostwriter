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


@router.post("/brands", response_model=BrandVoiceResponse, status_code=201, summary="Create brand voice", description="Create a brand voice profile with guidelines and optional sample content.")
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


@router.get("/brands", response_model=list[BrandVoiceResponse], summary="List brand voices", description="List all brand voice profiles with pagination.")
async def list_brands(
    limit: int = 50,
    offset: int = 0,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(BrandVoice).where(BrandVoice.account_id == account.id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/brands/{brand_id}", response_model=BrandVoiceResponse, summary="Get brand voice", description="Get a specific brand voice profile by ID.")
async def get_brand(
    brand_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    brand = await db.get(BrandVoice, brand_id)
    if not brand or brand.account_id != account.id:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.put("/brands/{brand_id}", response_model=BrandVoiceResponse, summary="Update brand voice", description="Update an existing brand voice profile.")
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


@router.delete("/brands/{brand_id}", status_code=204, summary="Delete brand voice", description="Delete a brand voice profile.")
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
