import uuid
from datetime import datetime
from pydantic import BaseModel


class AccountCreate(BaseModel):
    name: str


class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountCreateResponse(BaseModel):
    account: AccountResponse
    api_key: str  # only returned once at creation
