import hashlib

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.auth.service import authenticate, get_or_create_default_account
from app.models.account import Account

security = HTTPBearer(auto_error=False)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def get_current_account(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    db: AsyncSession = Depends(get_db),
) -> Account:
    if not settings.auth_enabled:
        if settings.self_host_api_key:
            # Check Bearer token first
            if credentials and credentials.credentials == settings.self_host_api_key:
                return await get_or_create_default_account(db)
            # Check session cookie (for UI/htmx requests)
            cookie = request.cookies.get("gw_session")
            if cookie and cookie == _hash_key(settings.self_host_api_key):
                return await get_or_create_default_account(db)
            raise HTTPException(status_code=401, detail="Missing or invalid API key")
        return await get_or_create_default_account(db)

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing API key")
    account = await authenticate(db, credentials.credentials)
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return account
