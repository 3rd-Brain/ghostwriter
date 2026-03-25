import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, ApiKey


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    return f"gw_{secrets.token_urlsafe(32)}"


async def create_account_with_key(db: AsyncSession, name: str, key_label: str = "default") -> tuple[Account, str]:
    account = Account(name=name)
    db.add(account)
    await db.flush()

    raw_key = generate_api_key()
    api_key = ApiKey(account_id=account.id, key_hash=hash_api_key(raw_key), label=key_label)
    db.add(api_key)
    await db.commit()
    await db.refresh(account)
    return account, raw_key


async def authenticate(db: AsyncSession, raw_key: str) -> Account | None:
    key_hash = hash_api_key(raw_key)
    stmt = (
        select(Account)
        .join(ApiKey)
        .where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
