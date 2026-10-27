"""Browser Integration Endpoints."""

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sahaay_core.adapters.browser.adapter import BrowserAdapter
from sahaay_core.api.v1.actions import evidence_ledger
from sahaay_core.api.v1.sessions import active_grants
from sahaay_core.api.v1.sources import context_store, source_manager
from sahaay_core.api.v1.tasks import orchestrator
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

router = APIRouter(prefix="/browser", tags=["Browser Bridge"])
adapter = BrowserAdapter()


class IngestObservationRequest(BaseModel):
    url: str
    title: str
    scrollPosition: Dict[str, int]
    documentDimensions: Dict[str, int]
    visibleTextExcerpt: str
    accessibleElements: Optional[List[Dict[str, Any]]] = None
    sessionId: Optional[UUID] = None
    taskId: Optional[UUID] = None


class ExecuteScrollActionRequest(BaseModel):
    sessionId: UUID
    taskId: UUID
    stepId: UUID
    url: str
    requestedDeltaY: int = 300
    preScrollY: int
    postScrollY: int


@router.post("/observe", response_model=Dict[str, Any])
async def ingest_tab_observation(req: IngestObservationRequest) -> Dict[str, Any]:
    """Ingests real observation from authorized browser tab and records facts into ContextStore."""
    try:
        obs_record = adapter.ingest_tab_observation(req.model_dump())

        # Register as permitted SourceReference
        source_ref = source_manager.register_source(
            source_type="browser_tab",
            uri=req.url,
            title=req.title,
            metadata={"documentDimensions": req.documentDimensions},
        )

        # Record structured context facts
        f1 = context_store.record_fact(
            fact_type=FactTypeEnum.OBSERVED,
            content=f"Authorized tab '{req.title}' loaded at {req.url}",
            source_reference_id=source_ref.sourceId,
            metadata={"scrollPosition": req.scrollPosition},
        )

        if req.visibleTextExcerpt:
            context_store.record_fact(
                fact_type=FactTypeEnum.SOURCE_EXTRACTED,
                content=req.visibleTextExcerpt,
                source_reference_id=source_ref.sourceId,
                derivation_ids=[f1.factId],
                metadata={"length": len(req.visibleTextExcerpt)},
            )

        return {
            "success": True,
            "observation": obs_record,
            "sourceId": str(source_ref.sourceId),
            "url": req.url,
            "title": req.title,
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.post("/action/scroll", response_model=Dict[str, Any])
async def execute_and_verify_scroll(
    req: ExecuteScrollActionRequest,
) -> Dict[str, Any]:
    """Proposes bounded scroll action, evaluates via ActionGate, independently verifies postcondition,

    and writes to EvidenceLedger.
    """
    task = orchestrator.get_task(req.taskId)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 1. PROPOSE ACTION
    action = ActionContract(
        actionId=uuid4(),
        actionType=ActionTypeEnum.SCROLL_BROWSER_TAB,
        target=req.url,
        parameters={"deltaY": req.requestedDeltaY},
        expectedPostcondition=f"scrolled by {req.requestedDeltaY}px",
        estimatedRisk="READ_ONLY",
    )

    # 2. AUTHORIZE (Action Gate)
    grants = active_grants.get(req.sessionId, [])
    policy_decision = ActionGate.evaluate(
        action=action,
        active_grants=grants,
        is_task_cancelled=(task.status.value == "CANCELLED"),
    )

    if policy_decision.decision != PolicyDecisionEnum.ALLOW:
        return {
            "authorized": False,
            "policyDecision": policy_decision.decision.value,
            "reason": policy_decision.reason,
            "verified": False,
        }

    # 3. EXECUTE & VERIFY
    actual_delta = req.postScrollY - req.preScrollY
    exec_result = ExecutionResult(
        executionId=uuid4(),
        actionId=action.actionId,
        isSuccess=True,
        durationMs=50.0,
        outputData={
            "preScrollY": req.preScrollY,
            "postScrollY": req.postScrollY,
            "actualDelta": actual_delta,
        },
    )

    # Check postcondition objectively
    is_verified = (actual_delta != 0) and (
        (req.requestedDeltaY > 0 and actual_delta > 0)
        or (req.requestedDeltaY < 0 and actual_delta < 0)
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

    # 4. RECORD TO EVIDENCE LEDGER
    evidence = evidence_ledger.record_evidence(
        task_id=req.taskId,
        step_id=req.stepId,
        action_id=action.actionId,
        verification_result=verification_result,
        narrative=(
            f"Bounded scroll executed: preScroll={req.preScrollY}px,"
            f" postScroll={req.postScrollY}px, delta={actual_delta}px."
            f" Status: {verification_status.value}"
        ),
    )

    return {
        "authorized": True,
        "policyDecision": policy_decision.decision.value,
        "verificationStatus": verification_result.status.value,
        "evidenceId": str(evidence.evidenceId),
        "actualDeltaY": actual_delta,
        "requestedDeltaY": req.requestedDeltaY,
        "details": verification_result.details,
    }
