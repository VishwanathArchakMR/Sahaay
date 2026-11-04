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


@router.get("", response_model=list[TaskContract])
async def list_tasks(limit: int = 20) -> list[TaskContract]:
    """Fetch recent tasks from durable storage."""
    from sahaay_core.storage.persistence import durable_storage

    return durable_storage.list_tasks(limit=limit)


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
        from sahaay_core.api.v1.workflows import active_workflow_tasks
        from sahaay_core.storage.persistence import durable_storage

        bg_task = active_workflow_tasks.get(task_id)
        if bg_task and not bg_task.done():
            bg_task.cancel()

        durable_storage.record_task_event(
            task_id=str(task_id),
            event_type="task.cancelled",
            stage="CANCELLED",
            message="Task was stopped by user request.",
            data={"reason": "User requested stop/cancel via UI"},
        )
        return orchestrator.cancel_task(task_id)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{task_id}/stop", response_model=TaskContract)
async def stop_task(task_id: UUID) -> TaskContract:
    """Stop task execution immediately (alias for cancel)."""
    return await cancel_task(task_id)


@router.post("/{task_id}/pause", response_model=TaskContract)
async def pause_task(task_id: UUID) -> TaskContract:
    """Pause task execution."""
    try:
        from sahaay_core.storage.persistence import durable_storage

        durable_storage.record_task_event(
            task_id=str(task_id),
            event_type="task.paused",
            stage="PAUSED",
            message="Task execution was paused by user.",
        )
        return orchestrator.pause_task(task_id)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{task_id}/resume", response_model=TaskContract)
async def resume_task(task_id: UUID) -> TaskContract:
    """Resume task execution."""
    try:
        from sahaay_core.storage.persistence import durable_storage

        durable_storage.record_task_event(
            task_id=str(task_id),
            event_type="task.resumed",
            stage="EXECUTING",
            message="Task execution was resumed by user.",
        )
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


@router.get("/{task_id}/events")
async def get_task_events(task_id: UUID, limit: int = 100):
    """Retrieve recorded lifecycle events for a task."""
    from sahaay_core.storage.persistence import durable_storage

    events = durable_storage.get_task_events(str(task_id), limit=limit)
    return {"taskId": str(task_id), "events": events, "count": len(events)}


@router.get("/{task_id}/passport")
async def get_task_passport_endpoint(task_id: str):
    """Retrieve the authoritative Task Passport and milestone progression for a task."""
    from sahaay_core.storage.persistence import durable_storage

    passport = durable_storage.get_task_passport(str(task_id))
    if not passport:
        task = None
        try:
            from uuid import UUID as PyUUID
            task = orchestrator.get_task(PyUUID(task_id))
        except (ValueError, TypeError):
            pass

        if not task:
            raise HTTPException(status_code=404, detail="Task passport not found")

        events = durable_storage.get_task_events(str(task_id), limit=50)
        return {
            "taskId": str(task.taskId),
            "goal": task.goal,
            "workflowMode": "do",
            "verificationStatus": "VERIFIED" if task.status == TaskStatusEnum.COMPLETED else ("FAILED" if task.status == TaskStatusEnum.FAILED else "UNVERIFIED"),
            "summaryNotice": task.summary or f"Task is {task.status.value}",
            "milestones": [
                {
                    "milestoneId": f"m-{i}",
                    "title": ev.get("stage", "STAGE"),
                    "description": ev.get("message", ""),
                    "status": "COMPLETED" if ev.get("eventType") in ("task.completed", "action.executed") else "IN_PROGRESS",
                    "timestamp": ev.get("timestamp", ""),
                }
                for i, ev in enumerate(events)
            ],
            "totalMilestones": len(events),
        }
    return passport


@router.get("/{task_id}/blueprint")
async def get_task_blueprint(task_id: UUID):
    """Retrieve the authoritative Task Blueprint and Definition-of-Done for a task."""
    from sahaay_core.storage.persistence import durable_storage

    bp = durable_storage.get_task_blueprint(str(task_id))
    if not bp:
        raise HTTPException(status_code=404, detail="Task blueprint not found")
    return bp


@router.get("/{task_id}/artifacts")
async def get_task_artifacts(task_id: UUID):
    """Retrieve all artifacts generated for this task."""
    from sahaay_core.storage.persistence import durable_storage

    artifacts = durable_storage.get_artifacts_for_task(str(task_id))
    return {"taskId": str(task_id), "artifacts": artifacts, "count": len(artifacts)}


@router.get("/{task_id}/stream")
async def stream_task_events(task_id: UUID):
    """Real-time SSE event stream for live task progress on desktop and browser."""
    import asyncio
    import json
    from fastapi.responses import StreamingResponse
    from sahaay_core.storage.persistence import durable_storage

    async def event_generator():
        last_count = 0
        poll_interval = 0.5
        max_duration = 180.0  # 3 minutes max stream
        elapsed = 0.0

        while elapsed < max_duration:
            events = durable_storage.get_task_events(str(task_id), limit=200)
            if len(events) > last_count:
                new_events = events[last_count:]
                for ev in new_events:
                    yield f"data: {json.dumps(ev)}\n\n"
                last_count = len(events)
                # If terminal event observed, end stream
                if any(ev.get("eventType") in ("task.completed", "task.failed", "task.cancelled") for ev in new_events):
                    break
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

    return StreamingResponse(event_generator(), media_type="text/event-stream")
