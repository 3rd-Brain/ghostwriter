import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountCreateResponse(BaseModel):
    account: AccountResponse
    api_key: str  # only returned once at creation
