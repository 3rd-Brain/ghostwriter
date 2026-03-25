import uuid
from datetime import datetime
from pydantic import BaseModel


class SourceContentCreate(BaseModel):
    content: str
    source: str = "manual"
    channel_source: str = "manual"
    metadata: dict | None = None


class SourceContentBatchItem(BaseModel):
    content: str
    source: str = "manual"
    channel_source: str = "manual"
    metadata: dict | None = None


class SourceContentBatchRequest(BaseModel):
    items: list[SourceContentBatchItem]


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
    limit: int = 5


class SourceContentSearchResponse(BaseModel):
    results: list[SourceContentResponse]


class TwitterImportRequest(BaseModel):
    profile_url: str
    max_tweets: int = 50


class TwitterImportResponse(BaseModel):
    imported_count: int
    items: list[SourceContentResponse]
