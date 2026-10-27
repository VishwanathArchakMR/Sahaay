"""Task Management Endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from sahaay_core.contracts.models import TaskContract, TaskStatusEnum
from sahaay_core.orchestration.orchestrator import InvalidStateTransitionError, TaskOrchestrator

router = APIRouter(prefix="/tasks", tags=["Tasks"])

# Module level orchestrator instance
orchestrator = TaskOrchestrator()


class CreateTaskRequest(BaseModel):
    sessionId: UUID
    goal: str
    taskType: str = "combined_retrieval_and_action"


class TransitionStateRequest(BaseModel):
    targetStatus: TaskStatusEnum


@router.post("", response_model=TaskContract, status_code=status.HTTP_201_CREATED)
async def create_task(req: CreateTaskRequest) -> TaskContract:
    """Create a new task."""
    return orchestrator.create_task(
        session_id=req.sessionId,
        goal=req.goal,
        task_type=req.taskType,
    )


@router.get("/{task_id}", response_model=TaskContract)
async def get_task(task_id: UUID) -> TaskContract:
    """Fetch task status and step history."""
    task = orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/transition", response_model=TaskContract)
async def transition_task(task_id: UUID, req: TransitionStateRequest) -> TaskContract:
    """Transition task status through state machine."""
    try:
        return orchestrator.transition_state(task_id, req.targetStatus)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{task_id}/cancel", response_model=TaskContract)
async def cancel_task(task_id: UUID) -> TaskContract:
    """Cancel task immediately and block subsequent actions."""
    try:
        return orchestrator.cancel_task(task_id)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{task_id}/pause", response_model=TaskContract)
async def pause_task(task_id: UUID) -> TaskContract:
    """Pause task execution."""
    try:
        return orchestrator.pause_task(task_id)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{task_id}/resume", response_model=TaskContract)
async def resume_task(task_id: UUID) -> TaskContract:
    """Resume task execution."""
    try:
        return orchestrator.resume_task(task_id)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{task_id}/handoff", response_model=TaskContract)
async def handoff_task(task_id: UUID) -> TaskContract:
    """Request human handoff."""
    try:
        return orchestrator.request_handoff(task_id)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
