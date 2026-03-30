from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.auth.service import authenticate, get_or_create_default_account
from app.models.account import Account

security = HTTPBearer(auto_error=False)


async def get_current_account(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    db: AsyncSession = Depends(get_db),
) -> Account:
    if not settings.auth_enabled:
        # Self-host mode: optionally require a static API key from .env
        if settings.self_host_api_key:
            if credentials is None:
                raise HTTPException(status_code=401, detail="Missing API key")
            if credentials.credentials != settings.self_host_api_key:
                raise HTTPException(status_code=401, detail="Invalid API key")
        return await get_or_create_default_account(db)

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing API key")
    account = await authenticate(db, credentials.credentials)
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return account
