from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_account
from app.models.account import Account
from app.providers import resolve_provider

router = APIRouter(tags=["templatize"])

TEMPLATIZER_SYSTEM_PROMPT = """Create a versatile social media post template by analyzing the content and extracting its structural patterns, emotional hooks, and rhetorical devices while removing the specific subject matter.

Steps:
1. Analyze the post's structure, formatting, and stylistic elements
2. Identify key components that make it engaging
3. Strip away specific content while preserving the structural framework
4. Mark variable elements with clear [placeholder] notation

Output only the template, nothing else."""


class TemplatizeRequest(BaseModel):
    content: str
    model: str = "claude-haiku-4-5-20251001"
    provider_key: str | None = None


class TemplatizeResponse(BaseModel):
    template: str


@router.post("/templatize", response_model=TemplatizeResponse)
async def templatize(
    body: TemplatizeRequest,
    account: Account = Depends(get_current_account),
):
    provider = resolve_provider(body.model)
    result = await provider.generate(
        model=body.model,
        system_prompt=TEMPLATIZER_SYSTEM_PROMPT,
        user_prompt=body.content,
        max_tokens=2048,
        temperature=0.7,
        api_key=body.provider_key,
    )
    return TemplatizeResponse(template=result.text)
