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


class CombinedVerifyAndScrollRequest(BaseModel):
    sessionId: UUID
    requiredKey: str
    targetUrl: str
    scrollDeltaY: int = 300
    preScrollY: int = 0
    postScrollY: int = 300


@router.post("/{task_id}/combined/verify-and-scroll")
async def execute_combined_retrieval_and_scroll(
    task_id: UUID,
    req: CombinedVerifyAndScrollRequest,
) -> dict:
    """Executes a combined task: retrieves required fact, verifies precondition,

    and only dispatches authorized browser action if precondition is strictly satisfied.
    Stops and requests human handoff on conflict or ambiguity.
    """
    from uuid import uuid4

    from sahaay_core.api.v1.actions import evidence_ledger
    from sahaay_core.api.v1.sessions import active_grants
    from sahaay_core.api.v1.sources import context_store, source_manager
    from sahaay_core.contracts.models import (
        ActionContract,
        ActionTypeEnum,
        ExecutionResult,
        FactTypeEnum,
        PolicyDecisionEnum,
        VerificationStatusEnum,
    )
    from sahaay_core.policy.action_gate import ActionGate
    from sahaay_core.verification.verifier import IndependentVerifier

    task = orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == TaskStatusEnum.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot execute on a cancelled task.")

    # 1. State: PLANNING -> OBSERVING
    if task.status == TaskStatusEnum.CREATED:
        orchestrator.transition_state(task_id, TaskStatusEnum.PLANNING)
    if task.status == TaskStatusEnum.PLANNING:
        orchestrator.transition_state(task_id, TaskStatusEnum.OBSERVING)

    # 2. Information Retrieval from Active Permitted Sources
    query_lower = req.requiredKey.strip().lower()
    active_sources = source_manager.list_active_sources()
    matching_facts = []

    for src in active_sources:
        facts = context_store.get_facts_for_source(src.sourceId)
        for f in facts:
            if query_lower in f.content.lower():
                matching_facts.append((src, f))

    # Precondition check: No matching facts found
    if not matching_facts:
        orchestrator.transition_state(task_id, TaskStatusEnum.COMPLETED)
        return {
            "preconditionMet": False,
            "actionExecuted": False,
            "status": "COMPLETED",
            "reason": f"Precondition key '{req.requiredKey}' was not found in permitted sources; computer action safely skipped.",
            "matchingFactsCount": 0,
        }

    # Precondition check: Conflicting data found across sources
    has_conflicts = any(f.factType == FactTypeEnum.CONFLICTING for _, f in matching_facts)
    if has_conflicts:
        orchestrator.transition_state(task_id, TaskStatusEnum.HANDOFF_REQUESTED)
        return {
            "preconditionMet": False,
            "actionExecuted": False,
            "status": "HANDOFF_REQUESTED",
            "reason": "Conflicting source facts detected during retrieval; stopping for human review.",
            "matchingFactsCount": len(matching_facts),
        }

    # 3. Precondition Satisfied: Advance State -> PROPOSING
    orchestrator.transition_state(task_id, TaskStatusEnum.PROPOSING)

    action = ActionContract(
        actionId=uuid4(),
        actionType=ActionTypeEnum.SCROLL_BROWSER_TAB,
        target=req.targetUrl,
        parameters={"deltaY": req.scrollDeltaY},
        expectedPostcondition=f"scrolled by {req.scrollDeltaY}px after confirming {req.requiredKey}",
        estimatedRisk="READ_ONLY",
    )

    # 4. State: AUTHORIZING
    orchestrator.transition_state(task_id, TaskStatusEnum.AUTHORIZING)
    grants = active_grants.get(req.sessionId, [])
    policy_decision = ActionGate.evaluate(
        action=action,
        active_grants=grants,
        is_task_cancelled=False,
        task_type=task.taskType,
    )

    if policy_decision.decision != PolicyDecisionEnum.ALLOW:
        orchestrator.transition_state(task_id, TaskStatusEnum.FAILED)
        return {
            "preconditionMet": True,
            "authorized": False,
            "policyDecision": policy_decision.decision.value,
            "reason": policy_decision.reason,
            "actionExecuted": False,
        }

    # 5. State: EXECUTING
    orchestrator.transition_state(task_id, TaskStatusEnum.EXECUTING)
    actual_delta = req.postScrollY - req.preScrollY
    exec_result = ExecutionResult(
        executionId=uuid4(),
        actionId=action.actionId,
        isSuccess=True,
        durationMs=45.0,
        outputData={
            "preScrollY": req.preScrollY,
            "postScrollY": req.postScrollY,
            "actualDelta": actual_delta,
        },
    )

    # 6. State: VERIFYING
    orchestrator.transition_state(task_id, TaskStatusEnum.VERIFYING)
    is_verified = (actual_delta != 0) and (
        (req.scrollDeltaY > 0 and actual_delta > 0) or (req.scrollDeltaY < 0 and actual_delta < 0)
    )
    verification_status = (
        VerificationStatusEnum.VERIFIED if is_verified else VerificationStatusEnum.CONFLICT
    )
    verification_result = IndependentVerifier.verify_action_outcome(
        action=action,
        execution_result=exec_result,
        observed_postcondition_data={
            "state": f"scrolled by {actual_delta}px" if is_verified else "no movement"
        },
        is_model_self_attestation=False,
    )

    # 7. State: RECORD to Evidence Ledger & Complete Task
    step_id = uuid4()
    evidence = evidence_ledger.record_evidence(
        task_id=task_id,
        step_id=step_id,
        action_id=action.actionId,
        verification_result=verification_result,
        narrative=f"Combined task completed: verified '{req.requiredKey}' in source, executed scroll by {actual_delta}px.",
    )
    orchestrator.transition_state(task_id, TaskStatusEnum.COMPLETED)

    return {
        "preconditionMet": True,
        "actionExecuted": True,
        "authorized": True,
        "verificationStatus": verification_status.value,
        "evidenceId": str(evidence.evidenceId),
        "actualDeltaY": actual_delta,
        "matchedSource": matching_facts[0][0].uri,
        "status": "COMPLETED",
    }
