"""Tests for Action Gate Policy Engine."""

from uuid import uuid4

from sahaay_core.contracts.models import (
    ActionContract,
    ActionTypeEnum,
    ConsentGrant,
    PolicyDecisionEnum,
)
from sahaay_core.policy.action_gate import ActionGate


def test_action_gate_denies_shell_and_arbitrary_commands():
    action = ActionContract(
        actionType=ActionTypeEnum.READ_FILE,
        target="C:\\Windows\\System32\\powershell.exe -Command rm -rf",
        expectedPostcondition="system pwned",
    )
    decision = ActionGate.evaluate(action=action, active_grants=[])
    assert decision.decision == PolicyDecisionEnum.DENY
    assert "forbidden" in decision.reason.lower()


def test_action_gate_requires_consent_for_mutation():
    action = ActionContract(
        actionType=ActionTypeEnum.CLICK_DESKTOP_CONTROL,
        target="Button[AutomationId='Submit']",
        expectedPostcondition="Submitted",
        estimatedRisk="MEDIUM",
    )
    # Without matching grant, MEDIUM/HIGH risk requests CLARIFY
    decision = ActionGate.evaluate(action=action, active_grants=[])
    assert decision.decision == PolicyDecisionEnum.CLARIFY
    assert decision.clarificationPrompt is not None

    # With explicit grant, action is ALLOWED
    grant = ConsentGrant(
        sessionId=uuid4(),
        scope="click_desktop_control",
        purpose="Form submission",
    )
    authorized_decision = ActionGate.evaluate(action=action, active_grants=[grant])
    assert authorized_decision.decision == PolicyDecisionEnum.ALLOW
