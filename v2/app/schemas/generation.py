import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ProviderKeys(BaseModel):
    anthropic: str | None = None
    openai: str | None = None
    google: str | None = None


class GenerateRequest(BaseModel):
    workflow_id: uuid.UUID

    # Content input
    content: str | None = None
    content_query: str | None = None

    # Template input
    template: str | None = None
    template_query: str | None = None
    template_count: int = Field(default=1, ge=1, le=10)

    # Context
    brand_id: uuid.UUID | None = None

    # Provider keys
    provider_keys: ProviderKeys | None = None


class StepUsage(BaseModel):
    step: int
    name: str
    model: str
    input_tokens: int
    output_tokens: int


class GenerationItem(BaseModel):
    id: uuid.UUID
    output: str
    template_used: str | None
    token_usage: dict


class GenerateResponse(BaseModel):
    generations: list[GenerationItem]


class GeneratedContentResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    brand_id: uuid.UUID | None
    input_content: str
    input_template: str | None
    output: str
    token_usage: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
