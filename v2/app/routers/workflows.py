import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_account
from app.models.account import Account
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse

router = APIRouter(tags=["workflows"])


@router.post("/workflows", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    workflow = Workflow(
        account_id=account.id,
        name=body.name,
        description=body.description,
        steps=[s.model_dump() for s in body.steps],
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.get("/workflows", response_model=list[WorkflowResponse])
async def list_workflows(
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(
            or_(Workflow.account_id == account.id, Workflow.account_id.is_(None))
        )
    )
    return result.scalars().all()


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    wf = await db.get(Workflow, workflow_id)
    if not wf or (wf.account_id is not None and wf.account_id != account.id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.put("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowUpdate,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    wf = await db.get(Workflow, workflow_id)
    if not wf or wf.account_id != account.id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    update_data = body.model_dump(exclude_unset=True)
    if "steps" in update_data:
        update_data["steps"] = [s.model_dump() for s in body.steps] if body.steps else []
    for field, value in update_data.items():
        setattr(wf, field, value)
    await db.commit()
    await db.refresh(wf)
    return wf


@router.delete("/workflows/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    wf = await db.get(Workflow, workflow_id)
    if not wf or wf.account_id != account.id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(wf)
    await db.commit()
