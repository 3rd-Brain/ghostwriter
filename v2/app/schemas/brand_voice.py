import uuid
from datetime import datetime
from pydantic import BaseModel


class BrandVoiceCreate(BaseModel):
    name: str
    voice_guidelines: str
    sample_content: str | None = None


class BrandVoiceUpdate(BaseModel):
    name: str | None = None
    voice_guidelines: str | None = None
    sample_content: str | None = None


class BrandVoiceResponse(BaseModel):
    id: uuid.UUID
    name: str
    voice_guidelines: str
    sample_content: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
