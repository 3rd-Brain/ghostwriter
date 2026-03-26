from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.auth import get_current_account, create_account_with_key
from app.schemas.account import AccountCreate, AccountCreateResponse, AccountResponse
from app.models.account import Account

router = APIRouter(tags=["accounts"])


@router.post("/accounts", response_model=AccountCreateResponse, status_code=201, summary="Create account", description="Create a new account and receive an API key. Only available when AUTH_ENABLED=true.")
async def create_account(body: AccountCreate, db: AsyncSession = Depends(get_db)):
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    account, raw_key = await create_account_with_key(db, body.name)
    return AccountCreateResponse(
        account=AccountResponse.model_validate(account),
        api_key=raw_key,
    )


@router.get("/accounts/me", response_model=AccountResponse, summary="Get current account", description="Get the authenticated account's details.")
async def get_me(account: Account = Depends(get_current_account)):
    return AccountResponse.model_validate(account)
