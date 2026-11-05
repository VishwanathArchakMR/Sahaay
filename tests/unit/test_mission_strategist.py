"""Unit tests for MissionStrategist and ActionGate production authorization."""

import sys
from pathlib import Path
from uuid import uuid4

# Ensure core/src is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core" / "src"))

import pytest
from sahaay_core.contracts.models import (
    ActionContract,
    ActionTypeEnum,
    ConsentGrant,
    PolicyDecisionEnum,
)
from sahaay_core.orchestration.mission_strategist import (
    mission_strategist,
)
from sahaay_core.policy.action_gate import ActionGate


@pytest.mark.asyncio
async def test_mission_strategist_direct_operation():
    strat = await mission_strategist.analyze_objective(
        task_id="test-task-1",
        session_id="test-session-1",
        goal="open notepad",
        allow_model_call=False,
        persist=False,
    )
    assert strat.depth_classification == "DIRECT_OPERATION"
    assert len(strat.execution_phases) >= 1
    assert len(strat.definition_of_done) >= 1
    assert "open notepad" in strat.original_objective.lower()

    prompt_text = strat.format_for_execution_prompt()
    assert "STRATEGIC MISSION PLAN" in prompt_text
    assert "DIRECT_OPERATION" in prompt_text


@pytest.mark.asyncio
async def test_mission_strategist_structured_task():
    strat = await mission_strategist.analyze_objective(
        task_id="test-task-2",
        session_id="test-session-2",
        goal="open notepad and write the meeting minutes",
        allow_model_call=False,
        persist=False,
    )
    assert strat.depth_classification in ("STRUCTURED_TASK", "COMPLEX_MISSION")
    assert len(strat.execution_phases) >= 2
    assert len(strat.definition_of_done) >= 1


@pytest.mark.asyncio
async def test_mission_strategist_complex_mission():
    strat = await mission_strategist.analyze_objective(
        task_id="test-task-3",
        session_id="test-session-3",
        goal="research renewable energy storage, compare top 3 battery chemistries, and generate report",
        allow_model_call=False,
        persist=False,
    )
    assert strat.depth_classification == "COMPLEX_MISSION"
    assert len(strat.execution_phases) >= 3
    assert len(strat.verification_criteria) >= 1
    prompt_text = strat.format_for_execution_prompt()
    assert "COMPLEX_MISSION" in prompt_text
    assert "DEFINITION OF DONE" in prompt_text


def test_action_gate_wildcard_grant_allows_production_actions():
    action = ActionContract(
        actionType=ActionTypeEnum.WINDOWS_LAUNCH_APP,
        target="notepad.exe",
        expectedPostcondition="Notepad launched",
        estimatedRisk="MEDIUM",
    )
    wildcard_grant = ConsentGrant(
        sessionId=uuid4(),
        scope="*",
        purpose="All automated actions authorized",
    )
    decision = ActionGate.evaluate(action=action, active_grants=[wildcard_grant])
    assert decision.decision == PolicyDecisionEnum.ALLOW
    assert "permitted allowlist" in decision.reason


def test_action_gate_desktop_automation_scope_allows_window_controls():
    action = ActionContract(
        actionType=ActionTypeEnum.WINDOWS_SET_CONTROL_TEXT,
        target="Edit",
        expectedPostcondition="Text entered",
        estimatedRisk="MEDIUM",
    )
    grant = ConsentGrant(
        sessionId=uuid4(),
        scope="desktop_automation",
        purpose="Desktop manipulation",
    )
    decision = ActionGate.evaluate(action=action, active_grants=[grant])
    assert decision.decision == PolicyDecisionEnum.ALLOW


def test_action_gate_browser_automation_scope_allows_navigation():
    action = ActionContract(
        actionType=ActionTypeEnum.BROWSER_NAVIGATE,
        target="https://www.youtube.com",
        expectedPostcondition="Tab navigated",
        estimatedRisk="MEDIUM",
    )
    grant = ConsentGrant(
        sessionId=uuid4(),
        scope="browser_automation",
        purpose="Browser control",
    )
    decision = ActionGate.evaluate(action=action, active_grants=[grant])
    assert decision.decision == PolicyDecisionEnum.ALLOW


def test_action_gate_blocks_forbidden_subsystems():
    action = ActionContract(
        actionType=ActionTypeEnum.WORKSPACE_RUN_CODE,
        target="powershell -Command Remove-Item -Recurse C:\\",
        expectedPostcondition="Destruction",
    )
    grant = ConsentGrant(
        sessionId=uuid4(),
        scope="*",
        purpose="All actions",
    )
    decision = ActionGate.evaluate(action=action, active_grants=[grant])
    assert decision.decision == PolicyDecisionEnum.DENY
    assert "forbidden execution subsystem" in decision.reason.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
