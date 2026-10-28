"""Unit tests for Baseten Muse Spark Open structured task planner."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sahaay_core.contracts.models import TaskContract
from sahaay_core.models.baseten.baseten_client import (
    BasetenApiResponse,
    BasetenAuthError,
    BasetenClient,
    BasetenRateLimitError,
)
from sahaay_core.models.baseten.muse_spark_open import (
    MuseSparkOpenPlanner,
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
async def test_baseten_client_status_when_unconfigured():
    client = BasetenClient(api_key="")
    assert client.is_configured is False
    status = await client.check_connectivity()
    assert status["configured"] is False
    assert status["status"] == "NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_baseten_client_mock_connectivity():
    client = BasetenClient(api_key="b10-test-key")
    assert client.is_configured is True

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200, json=lambda: {"choices": []}
        )
        status = await client.check_connectivity()
        assert status["configured"] is True
        assert status["status"] == "READY"


@pytest.mark.asyncio
async def test_baseten_client_error_handling():
    client = BasetenClient(api_key="b10-test-key")

    with patch("httpx.AsyncClient.post") as mock_post:
        # Test 401 Auth error
        mock_post.return_value = AsyncMock(status_code=401, text="Unauthorized")
        with pytest.raises(BasetenAuthError):
            await client.post_chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            )

        # Test 429 Rate limit retry & failure
        mock_post.return_value = AsyncMock(status_code=429, text="Rate limit exceeded")
        with pytest.raises(BasetenRateLimitError):
            await client.post_chat_completion(
                messages=[{"role": "user", "content": "hi"}], timeout_seconds=1.0
            )


@pytest.mark.asyncio
async def test_baseten_planner_local_fallback_when_unconfigured(mock_task):
    planner = MuseSparkOpenPlanner(client=BasetenClient(api_key=""))
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
async def test_baseten_planner_valid_plan_parsing(mock_task):
    client = BasetenClient(api_key="b10-valid-key")
    planner = MuseSparkOpenPlanner(client=client)

    sample_plan_json = """
    {
      "plan_id": "plan-1234",
      "task_goal": "Transfer bill to desktop",
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
          "requires_human_approval": false,
          "recovery_option": "halt_and_ask_user"
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
          "requires_human_approval": true,
          "recovery_option": "halt_and_ask_user"
        }
      ],
      "source_facts": {"amount": "2450.00"},
      "stop_conditions": ["Done"]
    }
    """

    with patch.object(
        planner.privacy_gateway, "evaluate_outbound_request"
    ) as mock_eval:
        from sahaay_core.contracts.models import DataClassificationEnum, PrivacyDecision

        mock_eval.return_value = PrivacyDecision(
            decisionId=uuid4(),
            allowTransmission=True,
            destination=client.base_url,
            dataClassification=DataClassificationEnum.INTERNAL,
            reason="Authorized",
        )

        with patch.object(client, "post_chat_completion") as mock_chat:
            mock_chat.return_value = BasetenApiResponse(
                status_code=200,
                data={
                    "choices": [
                        {"message": {"content": f"```json\n{sample_plan_json}\n```"}}
                    ]
                },
                latency_ms=120.0,
                usage={"prompt_tokens": 100, "completion_tokens": 80},
                model_id=client.default_model,
            )

            plan = await planner.generate_plan(
                task=mock_task,
                context="Context",
                source_facts={"amount": "2450.00"},
            )

            assert plan.validation_status == "VALIDATED"
            assert plan.plan_id == "plan-1234"
            assert len(plan.steps) == 2
            assert plan.steps[0].action_type == "get_tab_content"
            assert plan.steps[1].action_type == "set_control_text"


@pytest.mark.asyncio
async def test_baseten_planner_bounded_repair_on_malformed_json(mock_task):
    client = BasetenClient(api_key="b10-valid-key")
    planner = MuseSparkOpenPlanner(client=client)

    malformed_initial = """{ "plan_id": "p-1", "task_goal": "Goal", "steps": [ {"title": "broken..."""  # Missing closing brackets
    valid_repaired = """
    {
      "plan_id": "p-repaired",
      "task_goal": "Goal",
      "workflow_mode": "combined_retrieval_and_action",
      "steps": [
        {
          "step_id": "s-1",
          "title": "Repaired Step",
          "purpose": "Read content",
          "capability": "browser_tab_observe",
          "action_type": "get_tab_content",
          "target_surface": "browser_tab",
          "target_scope": "active_tab",
          "preconditions": [],
          "expected_postconditions": ["Read done"]
        }
      ],
      "source_facts": {}
    }
    """

    with patch.object(
        planner.privacy_gateway, "evaluate_outbound_request"
    ) as mock_eval:
        from sahaay_core.contracts.models import DataClassificationEnum, PrivacyDecision

        mock_eval.return_value = PrivacyDecision(
            decisionId=uuid4(),
            allowTransmission=True,
            destination=client.base_url,
            dataClassification=DataClassificationEnum.INTERNAL,
            reason="Authorized",
        )

        with patch.object(client, "post_chat_completion") as mock_chat:
            # First call returns malformed, second repair call returns valid repaired JSON
            mock_chat.side_effect = [
                BasetenApiResponse(
                    status_code=200,
                    data={"choices": [{"message": {"content": malformed_initial}}]},
                    latency_ms=100.0,
                    usage={},
                    model_id=client.default_model,
                ),
                BasetenApiResponse(
                    status_code=200,
                    data={"choices": [{"message": {"content": valid_repaired}}]},
                    latency_ms=110.0,
                    usage={},
                    model_id=client.default_model,
                ),
            ]

            plan = await planner.generate_plan(
                task=mock_task,
                context="Context",
                source_facts={},
            )

            assert plan.validation_status == "REPAIRED"
            assert plan.plan_id == "p-repaired"
            assert len(plan.steps) == 1


@pytest.mark.asyncio
async def test_baseten_planner_semantic_rejection_of_dangerous_actions(mock_task):
    client = BasetenClient(api_key="b10-valid-key")
    planner = MuseSparkOpenPlanner(client=client)

    # Injected dangerous shell execution proposal from untrusted LLM output
    dangerous_plan_json = """
    {
      "plan_id": "p-exploit",
      "task_goal": "Goal",
      "workflow_mode": "action_only",
      "steps": [
        {
          "step_id": "s-bad",
          "title": "Execute System Shell",
          "purpose": "Run powershell",
          "capability": "arbitrary_shell_execution",
          "action_type": "execute_shell",
          "target_surface": "system",
          "target_scope": "powershell.exe",
          "parameters": {"command": "powershell -c rmdir C:\\\\"}
        }
      ]
    }
    """

    with patch.object(
        planner.privacy_gateway, "evaluate_outbound_request"
    ) as mock_eval:
        from sahaay_core.contracts.models import DataClassificationEnum, PrivacyDecision

        mock_eval.return_value = PrivacyDecision(
            decisionId=uuid4(),
            allowTransmission=True,
            destination=client.base_url,
            dataClassification=DataClassificationEnum.INTERNAL,
            reason="Authorized",
        )

        with patch.object(client, "post_chat_completion") as mock_chat:
            mock_chat.return_value = BasetenApiResponse(
                status_code=200,
                data={"choices": [{"message": {"content": dangerous_plan_json}}]},
                latency_ms=90.0,
                usage={},
                model_id=client.default_model,
            )

            # Strict local validation must reject the dangerous proposal and fallback safely
            plan = await planner.generate_plan(
                task=mock_task,
                context="Context",
                source_facts={},
            )

            assert plan.validation_status == "LOCAL_FALLBACK"
            assert all(s.capability != "arbitrary_shell_execution" for s in plan.steps)
            assert all(s.action_type != "execute_shell" for s in plan.steps)
