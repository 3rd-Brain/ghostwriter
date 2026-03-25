import uuid
from datetime import datetime
from pydantic import BaseModel

from app.models.template import TemplateCategory


class TemplateCreate(BaseModel):
    content: str
    description: str = ""
    category: TemplateCategory = TemplateCategory.short_form


class TemplateResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    content: str
    description: str
    category: TemplateCategory
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateSearchRequest(BaseModel):
    query: str
    category: TemplateCategory | None = None
    limit: int = 5


class TemplateSearchResponse(BaseModel):
    templates: list[TemplateResponse]
