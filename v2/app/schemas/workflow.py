import uuid
from datetime import datetime
from pydantic import BaseModel


class WorkflowStep(BaseModel):
    order: int
    name: str
    model: str
    system_prompt: str
    user_prompt: str
    max_tokens: int = 4096
    temperature: float = 0.7


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
