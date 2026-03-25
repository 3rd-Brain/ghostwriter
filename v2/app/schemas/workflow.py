import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class WorkflowStep(BaseModel):
    order: int = Field(ge=1)
    name: str
    model: str
    system_prompt: str
    user_prompt: str
    max_tokens: int = Field(default=4096, ge=1, le=16384)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    steps: list[WorkflowStep]


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[WorkflowStep] | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    name: str
    description: str
    steps: list[WorkflowStep]
    created_at: datetime

    model_config = {"from_attributes": True}
