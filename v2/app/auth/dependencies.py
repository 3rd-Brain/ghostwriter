from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.service import authenticate
from app.models.account import Account

security = HTTPBearer()


async def get_current_account(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
) -> Account:
    account = await authenticate(db, credentials.credentials)
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return account
