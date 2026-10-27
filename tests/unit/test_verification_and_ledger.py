"""Tests for Independent Verification and Evidence Ledger."""

from uuid import uuid4

from sahaay_core.contracts.models import (
    ActionContract,
    ActionTypeEnum,
    ExecutionResult,
    VerificationStatusEnum,
)
from sahaay_core.ledger.evidence_ledger import EvidenceLedger
from sahaay_core.verification.verifier import IndependentVerifier


def test_model_self_attestation_is_strictly_rejected():
    """CRITICAL INVARIANT: A model cannot declare its own actions verified."""
    action = ActionContract(
        actionType=ActionTypeEnum.CLICK_DESKTOP_CONTROL,
        target="Button[AutomationId='Confirm']",
        expectedPostcondition="dialog closed",
    )
    execution_result = ExecutionResult(
        actionId=action.actionId,
        isSuccess=True,
        durationMs=150.0,
    )

    result = IndependentVerifier.verify_action_outcome(
        action=action,
        execution_result=execution_result,
        observed_postcondition_data={"state": "dialog closed"},
        is_model_self_attestation=True,  # Model claims it worked
    )

    assert result.status == VerificationStatusEnum.UNVERIFIED
    assert "rejected" in result.details.lower()


def test_independent_verification_success_and_conflict():
    action = ActionContract(
        actionType=ActionTypeEnum.NAVIGATE_BROWSER_TAB,
        target="https://example.com/checkout",
        expectedPostcondition="checkout page loaded",
    )
    execution_result = ExecutionResult(
        actionId=action.actionId,
        isSuccess=True,
        durationMs=300.0,
    )

    # 1. State conflict
    conflict_result = IndependentVerifier.verify_action_outcome(
        action=action,
        execution_result=execution_result,
        observed_postcondition_data={"state": "error 404 not found"},
    )
    assert conflict_result.status == VerificationStatusEnum.CONFLICT

    # 2. Verified match
    verified_result = IndependentVerifier.verify_action_outcome(
        action=action,
        execution_result=execution_result,
        observed_postcondition_data={"state": "checkout page loaded"},
    )
    assert verified_result.status == VerificationStatusEnum.VERIFIED


def test_evidence_ledger_immutability():
    ledger = EvidenceLedger()
    task_id = uuid4()
    step_id = uuid4()
    action = ActionContract(
        actionType=ActionTypeEnum.READ_FILE,
        target="data.csv",
        expectedPostcondition="read",
    )
    exec_res = ExecutionResult(actionId=action.actionId, isSuccess=True, durationMs=10)
    verif = IndependentVerifier.verify_action_outcome(
        action=action,
        execution_result=exec_res,
        observed_postcondition_data={"state": "verified"},
    )

    evidence = ledger.record_evidence(
        task_id=task_id,
        step_id=step_id,
        action_id=action.actionId,
        verification_result=verif,
    )

    records = ledger.get_evidence_for_task(task_id)
    assert len(records) == 1
    assert records[0].evidenceId == evidence.evidenceId
    assert records[0].verificationResultId == verif.verificationId
