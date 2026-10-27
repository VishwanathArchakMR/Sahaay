"""Tests for Shared Contract Validation."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sahaay_core.contracts.models import (
    ActionContract,
    ActionTypeEnum,
    ContextFact,
    FactTypeEnum,
    VerificationResult,
    VerificationStatusEnum,
)


def test_action_contract_valid():
    action = ActionContract(
        actionType=ActionTypeEnum.READ_FILE,
        target="C:\\docs\\report.txt",
        expectedPostcondition="File content retrieved",
        estimatedRisk="READ_ONLY",
    )
    assert action.actionType == ActionTypeEnum.READ_FILE
    assert action.estimatedRisk == "READ_ONLY"


def test_action_contract_rejects_invalid_action_type():
    with pytest.raises(ValidationError):
        ActionContract(
            actionType="arbitrary_powershell_execution",  # Invalid enum value
            target="malicious",
            expectedPostcondition="pwned",
        )


def test_action_contract_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ActionContract(
            actionType=ActionTypeEnum.READ_FILE,
            target="test.txt",
            expectedPostcondition="read",
            unexpected_field="disallowed",
        )


def test_context_fact_requires_valid_enum_and_range():
    with pytest.raises(ValidationError):
        ContextFact(
            factType="invalid_fact_type",
            content="Some fact",
            sourceReferenceId=uuid4(),
        )

    # Confidence score must be between 0.0 and 1.0
    with pytest.raises(ValidationError):
        ContextFact(
            factType=FactTypeEnum.OBSERVED,
            content="Some fact",
            sourceReferenceId=uuid4(),
            confidenceScore=1.5,
        )


def test_verification_result_valid_and_invalid():
    res = VerificationResult(
        actionId=uuid4(),
        status=VerificationStatusEnum.VERIFIED,
        verifierType="deterministic_state_check",
        details="Matches hash",
    )
    assert res.status == VerificationStatusEnum.VERIFIED

    with pytest.raises(ValidationError):
        VerificationResult(
            actionId=uuid4(),
            status="SUCCESS_DECLARATION",  # Invalid enum value
            verifierType="deterministic_state_check",
            details="fake",
        )
