import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class SourceContentCreate(BaseModel):
    content: str = Field(min_length=1)
    source: str = "manual"
    channel_source: str = "manual"
    metadata: dict | None = None


class SourceContentBatchItem(BaseModel):
    content: str = Field(min_length=1)
    source: str = "manual"
    channel_source: str = "manual"
    metadata: dict | None = None


class SourceContentBatchRequest(BaseModel):
    items: list[SourceContentBatchItem] = Field(max_length=100)


class SourceContentResponse(BaseModel):
    id: uuid.UUID
    content: str
    source: str
    channel_source: str
    metadata: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceContentSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)


class SourceContentSearchResponse(BaseModel):
    results: list[SourceContentResponse]


class TwitterImportRequest(BaseModel):
    profile_url: str
    max_tweets: int = Field(default=50, ge=1, le=500)


class TwitterImportResponse(BaseModel):
    imported_count: int
    items: list[SourceContentResponse]
