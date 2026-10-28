"""Unit tests for Meta Muse Spark 1.3 structured task planner."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sahaay_core.contracts.models import DataClassificationEnum, PrivacyDecision, TaskContract
from sahaay_core.models.meta.client import MetaApiResponse, MetaClient
from sahaay_core.models.meta.muse_spark import (
    MuseSparkClient,
)


@pytest.fixture
def mock_task() -> TaskContract:
    return TaskContract(
        taskId=uuid4(),
        sessionId=uuid4(),
        goal="Transfer electricity bill amount to desktop notepad",
        taskType="combined_retrieval_and_action",
    )


@pytest.mark.asyncio
async def test_muse_spark_client_status_when_unconfigured():
    client = MetaClient(api_key="")
    assert client.is_configured is False
    status = await client.check_connectivity()
    assert status["isConfigured"] is False
    assert status["status"] == "NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_muse_spark_planner_local_fallback_when_unconfigured(mock_task):
    planner = MuseSparkClient(client=MetaClient(api_key=""))
    plan = await planner.generate_plan(
        task=mock_task,
        context="Synthetic test context",
        source_facts={"consumer_name": "Aarav Sharma", "amount_due": "INR 2,450.00"},
    )

    assert plan.validation_status == "LOCAL_FALLBACK"
    assert len(plan.steps) >= 2
    assert any(s.action_type == "set_control_text" for s in plan.steps)
    assert any(s.action_type == "get_control_text" for s in plan.steps)


@pytest.mark.asyncio
async def test_muse_spark_planner_valid_plan_parsing(mock_task):
    meta_client = MetaClient(api_key="meta-valid-test-key")
    planner = MuseSparkClient(client=meta_client)

    sample_plan = {
        "plan_id": "plan-meta-spark-1234",
        "task_goal": "Transfer bill to desktop notepad",
        "workflow_mode": "combined_retrieval_and_action",
        "steps": [
            {
                "step_id": "s-1",
                "title": "Observe Bill",
                "purpose": "Read web page",
                "capability": "browser_tab_observe",
                "action_type": "get_tab_content",
                "target_surface": "browser_tab",
                "target_scope": "active_tab",
                "preconditions": [],
                "expected_postconditions": ["text captured"],
                "requires_human_approval": False,
                "recovery_option": "halt_and_ask_user",
                "parameters": {},
            },
            {
                "step_id": "s-2",
                "title": "Set Text",
                "purpose": "Write to Notepad",
                "capability": "windows_set_control_text",
                "action_type": "set_control_text",
                "target_surface": "desktop_window",
                "target_scope": "Notepad",
                "preconditions": ["Notepad running"],
                "expected_postconditions": ["Text set"],
                "requires_human_approval": True,
                "recovery_option": "halt_and_ask_user",
                "parameters": {"control_name": "Editor", "field_name": "bill_summary"},
            },
        ],
        "source_facts": {"amount": "2450.00"},
        "stop_conditions": ["Done"],
    }

    import json

    raw_json_str = json.dumps(sample_plan)

    with patch.object(planner.privacy_gateway, "evaluate_outbound_request") as mock_eval:
        mock_eval.return_value = PrivacyDecision(
            decisionId=uuid4(),
            allowTransmission=True,
            destination="https://api.meta.ai/v1",
            dataClassification=DataClassificationEnum.INTERNAL,
            reason="Authorized for task planning",
        )

        with patch.object(meta_client, "post_endpoint") as mock_post:
            mock_post.return_value = MetaApiResponse(
                status_code=200,
                data={"choices": [{"message": {"content": raw_json_str}}]},
                latency_ms=120.0,
                model_id="muse-spark-1.3",
            )

            plan = await planner.generate_plan(
                task=mock_task,
                context="Context from browser",
                source_facts={"amount": "2450.00"},
            )

            assert plan.validation_status == "VALIDATED"
            assert plan.plan_id == "plan-meta-spark-1234"
            assert len(plan.steps) == 2
            assert plan.steps[0].action_type == "get_tab_content"
            assert plan.steps[1].action_type == "set_control_text"


@pytest.mark.asyncio
async def test_muse_spark_planner_semantic_rejection_of_dangerous_actions(mock_task):
    meta_client = MetaClient(api_key="meta-valid-test-key")
    planner = MuseSparkClient(client=meta_client)

    dangerous_plan = {
        "plan_id": "plan-dangerous-injected",
        "task_goal": "Transfer bill to desktop notepad",
        "workflow_mode": "combined_retrieval_and_action",
        "steps": [
            {
                "step_id": "s-bad",
                "title": "Execute System Shell",
                "purpose": "Run powershell",
                "capability": "arbitrary_shell_execution",
                "action_type": "execute_shell",
                "target_surface": "system",
                "target_scope": "powershell.exe",
                "preconditions": [],
                "expected_postconditions": [],
                "requires_human_approval": False,
                "recovery_option": "halt_and_ask_user",
                "parameters": {"command": "powershell -c rmdir C:\\"},
            }
        ],
        "source_facts": {},
        "stop_conditions": [],
    }

    import json

    raw_json_str = json.dumps(dangerous_plan)

    with patch.object(planner.privacy_gateway, "evaluate_outbound_request") as mock_eval:
        mock_eval.return_value = PrivacyDecision(
            decisionId=uuid4(),
            allowTransmission=True,
            destination="https://api.meta.ai/v1",
            dataClassification=DataClassificationEnum.INTERNAL,
            reason="Authorized",
        )

        with patch.object(meta_client, "post_endpoint") as mock_post:
            mock_post.return_value = MetaApiResponse(
                status_code=200,
                data={"choices": [{"message": {"content": raw_json_str}}]},
                latency_ms=90.0,
                model_id="muse-spark-1.3",
            )

            # Strict local validation must reject the dangerous proposal and fall back safely
            plan = await planner.generate_plan(
                task=mock_task,
                context="Context",
                source_facts={},
            )

            assert plan.validation_status == "LOCAL_FALLBACK"
            assert all(s.capability != "arbitrary_shell_execution" for s in plan.steps)
            assert all(s.action_type != "execute_shell" for s in plan.steps)


def test_muse_spark_prompt_generation(mock_task):
    planner = MuseSparkClient(client=MetaClient(api_key=""))
    prompt = planner.build_planning_prompt(
        user_goal=mock_task.goal,
        task_contract=mock_task,
        context="Account: BLR-UTIL-98421 Amount: INR 2,450.00",
        source_facts={"account": "BLR-UTIL-98421", "amount": "INR 2,450.00"},
    )
    assert "Meta Muse Spark 1.3" in prompt
    assert "browser_tab_observe" in prompt
    assert "windows_set_control_text" in prompt
