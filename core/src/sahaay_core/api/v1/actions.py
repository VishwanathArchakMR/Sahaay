"""Action Gate and Verification Endpoints."""

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sahaay_core.api.v1.sessions import active_grants
from sahaay_core.api.v1.tasks import orchestrator
from sahaay_core.contracts.models import (
    ActionContract,
    ExecutionResult,
    PolicyDecision,
    VerificationResult,
)
from sahaay_core.ledger.evidence_ledger import EvidenceLedger
from sahaay_core.verification.verifier import IndependentVerifier

router = APIRouter(prefix="/actions", tags=["Actions & Verification"])

evidence_ledger = EvidenceLedger()


class ProposeActionRequest(BaseModel):
    taskId: UUID
    stepId: UUID
    action: ActionContract


class VerifyActionRequest(BaseModel):
    taskId: UUID
    stepId: UUID
    action: ActionContract
    executionResult: ExecutionResult
    observedPostconditionData: Optional[Dict[str, Any]] = None
    isModelSelfAttestation: bool = False


@router.post("/propose", response_model=PolicyDecision)
async def propose_action(req: ProposeActionRequest) -> PolicyDecision:
    """Propose an action and evaluate authorization through Action Gate."""
    task = orchestrator.get_task(req.taskId)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    grants = active_grants.get(task.sessionId, [])
    decision = orchestrator.propose_action(
        task_id=req.taskId,
        step_id=req.stepId,
        action=req.action,
        active_grants=grants,
    )
    return decision


@router.post("/verify", response_model=VerificationResult)
async def verify_action(req: VerifyActionRequest) -> VerificationResult:
    """Perform independent verification of action execution.

    Model self-attestation is strictly rejected.
    """
    result = IndependentVerifier.verify_action_outcome(
        action=req.action,
        execution_result=req.executionResult,
        observed_postcondition_data=req.observedPostconditionData,
        is_model_self_attestation=req.isModelSelfAttestation,
    )

    # Record in evidence ledger
    evidence_ledger.record_evidence(
        task_id=req.taskId,
        step_id=req.stepId,
        action_id=req.action.actionId,
        verification_result=result,
        narrative=f"Verified through verifier '{result.verifierType}'. Status: {result.status.value}",
    )

    return result
