"""Muse Spark Open (Baseten) Planner Integration.

Implements structured planning over Baseten Model API with:
- Strict local Pydantic schema validation (compensating for non-enforced provider schemas).
- At most one bounded repair attempt for syntactic failures.
- Semantic capability and Action Gate allowlist verification.
- Deterministic offline fallback preserving the OBSERVE -> PROPOSE -> AUTHORIZE -> EXECUTE -> VERIFY -> RECORD lifecycle.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from sahaay_core.contracts.models import (
    ActionTypeEnum,
    ConsentGrant,
    TaskContract,
)
from sahaay_core.models.baseten.baseten_client import (
    BasetenClient,
    BasetenError,
)
from sahaay_core.privacy.privacy_gateway import PrivacyGateway

logger = logging.getLogger(__name__)


class PlanStepProposal(BaseModel):
    """Structured proposal for an individual task milestone."""

    step_id: str = Field(default_factory=lambda: f"step-{uuid4().hex[:8]}")
    title: str = Field(description="Clear title in ordinary language")
    purpose: str = Field(description="Purpose of this step in achieving the goal")
    capability: str = Field(description="Required registered capability")
    action_type: str = Field(description="Action contract type enum string")
    target_surface: str = Field(description="browser_tab, desktop_window, or local_store")
    target_scope: str = Field(description="Specific target identifier, domain, or control name")
    preconditions: List[str] = Field(default_factory=list)
    expected_postconditions: List[str] = Field(default_factory=list)
    requires_human_approval: bool = Field(default=False)
    recovery_option: str = Field(default="halt_and_ask_user")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class StructuredTaskPlan(BaseModel):
    """Complete structured plan proposed by Muse Spark Open."""

    plan_id: str = Field(default_factory=lambda: f"plan-{uuid4().hex[:8]}")
    task_goal: str
    workflow_mode: str
    steps: List[PlanStepProposal]
    source_facts: Dict[str, Any] = Field(default_factory=dict)
    stop_conditions: List[str] = Field(default_factory=list)
    model_provider: str = "baseten_muse_spark_open"
    model_id: str = "meta-models/muse-spark-open"
    validation_status: str = "VALIDATED"  # VALIDATED | REPAIRED | REJECTED | LOCAL_FALLBACK
    latency_ms: float = 0.0


# Registered safe application capabilities
REGISTERED_CAPABILITIES = {
    "browser_tab_observe",
    "browser_fill_form",
    "browser_get_values",
    "browser_scroll",
    "windows_inspect_window",
    "windows_set_control_text",
    "windows_get_control_text",
    "document_ingest_chunk",
    "verify_readback",
    "user_authorization",
}

# Permitted action types mapped from ActionTypeEnum
PERMITTED_ACTION_TYPES = {e.value for e in ActionTypeEnum} | {"user_authorization"}



class MuseSparkOpenPlanner:
    """Task planner using Muse Spark Open via Baseten with local schema enforcement."""

    def __init__(self, client: Optional[BasetenClient] = None) -> None:
        self.client = client or BasetenClient()
        self.privacy_gateway = PrivacyGateway()

    async def generate_plan(
        self,
        task: TaskContract,
        context: str,
        source_facts: Dict[str, Any],
        active_grants: Optional[List[ConsentGrant]] = None,
    ) -> StructuredTaskPlan:
        """Generates and strictly validates a structured plan.

        Respects local-only mode and privacy gateway fail-closed defaults.
        """
        start_time = time.perf_counter()
        active_grants = active_grants or []

        # 1. Privacy Gateway Check
        privacy_eval = self.privacy_gateway.evaluate_outbound_request(
            destination=self.client.base_url,
            purpose="task_planning",
            content=f"{task.goal}\n{context}",
            active_grants=active_grants,
        )

        if not privacy_eval.allowTransmission or not self.client.is_configured:
            logger.info(
                "Outbound plan transmission not authorized or client unconfigured; using local plan generator."
            )
            plan = self._generate_deterministic_local_plan(task, source_facts)
            plan.latency_ms = (time.perf_counter() - start_time) * 1000
            return plan

        # 2. Build Structured Planning Prompt
        system_prompt = (
            "You are Muse Spark Open, a system-wide desktop and browser task planner for Sahaay.\n"
            "Produce ONLY valid JSON conforming exactly to this JSON schema without markdown prose:\n"
            "{\n"
            '  "plan_id": "string",\n'
            '  "task_goal": "string",\n'
            '  "workflow_mode": "combined_retrieval_and_action | action_only | retrieval_only",\n'
            '  "steps": [\n'
            "    {\n"
            '      "step_id": "string",\n'
            '      "title": "string",\n'
            '      "purpose": "string",\n'
            '      "capability": "browser_tab_observe | browser_fill_form | windows_set_control_text | verify_readback | user_authorization",\n'
            '      "action_type": "observe_browser_tab | fill_form_fields | set_control_text | get_control_text | get_field_values",\n'
            '      "target_surface": "browser_tab | desktop_window | local_store",\n'
            '      "target_scope": "string",\n'
            '      "preconditions": ["string"],\n'
            '      "expected_postconditions": ["string"],\n'
            '      "requires_human_approval": true,\n'
            '      "recovery_option": "halt_and_ask_user",\n'
            '      "parameters": {}\n'
            "    }\n"
            "  ],\n"
            '  "source_facts": {},\n'
            '  "stop_conditions": ["string"]\n'
            "}\n"
            "Do NOT include shell execution or unrestricted commands. Every action must specify exact target and verification criteria."
        )

        user_content = (
            f"Goal: {task.goal}\n"
            f"Mode: {task.taskType}\n"
            f"Available Facts: {json.dumps(source_facts)}\n"
            f"Context: {context[:1000]}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # 3. Call Baseten API
        try:
            res = await self.client.post_chat_completion(
                messages=messages,
                model=self.client.default_model,
                max_tokens=1500,
                temperature=0.1,
            )
            raw_content = res.data.get("choices", [{}])[0].get("message", {}).get("content", "")
            latency_ms = (time.perf_counter() - start_time) * 1000

            # 4. Strict Local Parsing & Validation
            plan_obj, validation_status = await self._parse_and_validate_with_repair(
                raw_content=raw_content,
                task_goal=task.goal,
                workflow_mode=str(task.taskType),
                source_facts=source_facts,
            )


            if plan_obj:
                # 5. Semantic Policy Validation
                is_semantically_valid = self._validate_semantic_policy(plan_obj)
                if is_semantically_valid:
                    plan_obj.latency_ms = latency_ms
                    plan_obj.validation_status = validation_status
                    plan_obj.model_id = self.client.default_model
                    return plan_obj
                else:
                    logger.warning(
                        "Muse Spark Open plan failed semantic policy checks; falling back."
                    )

        except BasetenError as b_err:
            logger.warning("Baseten planning error (%s); falling back to local planner.", b_err)
        except Exception as ex:
            logger.warning("Unexpected error during Baseten planning (%s); falling back.", ex)

        # Fallback to deterministic plan
        fallback_plan = self._generate_deterministic_local_plan(task, source_facts)
        fallback_plan.latency_ms = (time.perf_counter() - start_time) * 1000
        return fallback_plan

    async def _parse_and_validate_with_repair(
        self,
        raw_content: str,
        task_goal: str,
        workflow_mode: str,
        source_facts: Dict[str, Any],
    ) -> tuple[Optional[StructuredTaskPlan], str]:
        """Attempts Pydantic parsing with at most one bounded repair attempt."""
        cleaned = self._clean_json_markdown(raw_content)

        # Attempt 1: Direct parse
        try:
            data = json.loads(cleaned)
            plan = StructuredTaskPlan.model_validate(data)
            return plan, "VALIDATED"
        except Exception as parse_err:
            logger.info(
                "Initial plan parsing failed (%s). Attempting bounded 1-time repair...", parse_err
            )

        # Attempt 2: Bounded repair request
        repair_messages = [
            {
                "role": "system",
                "content": (
                    "You are a JSON repair tool. Return ONLY the corrected, clean JSON string with matching brackets "
                    "for the following invalid output, matching the schema strictly. No explanation."
                ),
            },
            {"role": "user", "content": f"Fix this malformed JSON:\n{raw_content[:2000]}"},
        ]
        try:
            repair_res = await self.client.post_chat_completion(
                messages=repair_messages,
                max_tokens=1500,
                temperature=0.0,
            )
            repaired_text = (
                repair_res.data.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            repaired_clean = self._clean_json_markdown(repaired_text)
            repaired_data = json.loads(repaired_clean)
            repaired_plan = StructuredTaskPlan.model_validate(repaired_data)
            logger.info("Plan successfully repaired by bounded repair attempt.")
            return repaired_plan, "REPAIRED"
        except Exception as repair_err:
            logger.warning("Bounded repair attempt failed (%s). Rejecting model plan.", repair_err)
            return None, "REJECTED"

    def _validate_semantic_policy(self, plan: StructuredTaskPlan) -> bool:
        """Validates that proposed operations are within registered capabilities and permitted actions."""
        if not plan.steps:
            return False

        for step in plan.steps:
            # 1. Capability must be registered
            if step.capability not in REGISTERED_CAPABILITIES:
                logger.warning("Unregistered capability requested: %s", step.capability)
                return False

            # 2. Action type must be permitted
            if step.action_type not in PERMITTED_ACTION_TYPES:
                logger.warning("Prohibited action type requested: %s", step.action_type)
                return False

            # 3. Prohibit dangerous parameters
            for val in step.parameters.values():
                val_str = str(val).lower()
                if any(
                    x in val_str for x in ["powershell", "cmd.exe", "rmdir", "delete", "format"]
                ):
                    logger.warning(
                        "Potentially dangerous command detected in plan parameter: %s", val_str
                    )
                    return False

        return True

    def _clean_json_markdown(self, text: str) -> str:
        """Strips markdown code fences and returns raw JSON text."""
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    def _generate_deterministic_local_plan(
        self,
        task: TaskContract,
        source_facts: Dict[str, Any],
    ) -> StructuredTaskPlan:
        """Generates a truthful, deterministic offline plan adhering to the execution lifecycle."""
        goal_lower = task.goal.lower()

        # Check workflow direction
        is_browser_to_desktop = "desktop" in goal_lower or "notepad" in goal_lower
        is_desktop_to_browser = (
            "form" in goal_lower or "browser" in goal_lower and not is_browser_to_desktop
        )

        if is_browser_to_desktop:
            steps = [
                PlanStepProposal(
                    step_id="step-b2d-1",
                    title="Observe Active Utility Bill Tab",
                    purpose="Capture DOM elements and text from authorized browser tab",
                    capability="browser_tab_observe",
                    action_type=ActionTypeEnum.GET_TAB_CONTENT.value,
                    target_surface="browser_tab",
                    target_scope="active_tab",
                    preconditions=["Browser tab loaded with utility bill"],
                    expected_postconditions=["DOM elements and bill amounts extracted"],
                    requires_human_approval=False,
                ),
                PlanStepProposal(
                    step_id="step-b2d-2",
                    title="User Authorization for Desktop Modification",
                    purpose="Obtain explicit approval to populate Windows desktop target",
                    capability="user_authorization",
                    action_type="user_authorization",
                    target_surface="desktop_window",
                    target_scope="Notepad",
                    preconditions=["Extracted facts validated against provenance"],
                    expected_postconditions=["User grants consent for desktop entry"],
                    requires_human_approval=True,
                ),
                PlanStepProposal(
                    step_id="step-b2d-3",
                    title="Populate Desktop Application Control",
                    purpose="Set control text in target Windows application via UI Automation",
                    capability="windows_set_control_text",
                    action_type=ActionTypeEnum.SET_CONTROL_TEXT.value,
                    target_surface="desktop_window",
                    target_scope="Notepad",
                    parameters={"control_name": "Editor", "field_name": "bill_summary"},
                    preconditions=["Target window is in foreground", "Consent granted"],
                    expected_postconditions=["Control text updated with verified values"],
                    requires_human_approval=False,
                ),
                PlanStepProposal(
                    step_id="step-b2d-4",
                    title="Independent Readback Verification",
                    purpose="Read back actual text from desktop control and verify exact match",
                    capability="verify_readback",
                    action_type=ActionTypeEnum.GET_CONTROL_TEXT.value,
                    target_surface="desktop_window",
                    target_scope="Notepad",
                    preconditions=["Desktop write operation completed"],
                    expected_postconditions=["Observed text equals expected bill summary"],
                    requires_human_approval=False,
                ),
            ]
        elif is_desktop_to_browser:
            steps = [
                PlanStepProposal(
                    step_id="step-d2b-1",
                    title="Ingest Local Invoice Source",
                    purpose="Read structured facts from permitted local invoice file",
                    capability="document_ingest_chunk",
                    action_type=ActionTypeEnum.READ_FILE.value,
                    target_surface="local_store",
                    target_scope="invoice_data.json",
                    preconditions=["File exists and user selected"],
                    expected_postconditions=["Invoice fields loaded with SHA-256 checksum"],
                    requires_human_approval=False,
                ),
                PlanStepProposal(
                    step_id="step-d2b-2",
                    title="User Authorization for Form Auto-Fill",
                    purpose="Obtain explicit approval to fill target browser payment form",
                    capability="user_authorization",
                    action_type="user_authorization",
                    target_surface="browser_tab",
                    target_scope="bill_pay_form.html",
                    preconditions=["Source facts mapped to form control IDs"],
                    expected_postconditions=["User approves field population"],
                    requires_human_approval=True,
                ),
                PlanStepProposal(
                    step_id="step-d2b-3",
                    title="Populate Browser Form Controls",
                    purpose="Fill designated input controls via extension content script",
                    capability="browser_fill_form",
                    action_type=ActionTypeEnum.FILL_FORM_FIELDS.value,
                    target_surface="browser_tab",
                    target_scope="bill_pay_form.html",
                    parameters={"auto_submit": False},
                    preconditions=["Browser tab has matching input elements"],
                    expected_postconditions=["Input elements populated with invoice values"],
                    requires_human_approval=False,
                ),
                PlanStepProposal(
                    step_id="step-d2b-4",
                    title="Verify DOM Field Values",
                    purpose="Read back actual input values from DOM to verify equality",
                    capability="browser_get_values",
                    action_type=ActionTypeEnum.GET_FIELD_VALUES.value,
                    target_surface="browser_tab",
                    target_scope="bill_pay_form.html",
                    preconditions=["Form fill dispatch completed"],
                    expected_postconditions=["DOM values match invoice source facts"],
                    requires_human_approval=False,
                ),
            ]
        else:
            steps = [
                PlanStepProposal(
                    step_id="step-gen-1",
                    title="Observe Requested Context",
                    purpose="Read current surface state",
                    capability="browser_tab_observe",
                    action_type=ActionTypeEnum.GET_TAB_CONTENT.value,
                    target_surface="browser_tab",
                    target_scope="active_context",
                    preconditions=[],
                    expected_postconditions=["Observed context captured"],
                    requires_human_approval=False,
                ),
                PlanStepProposal(
                    step_id="step-gen-2",
                    title="Independent Verification",
                    purpose="Verify observed state against criteria",
                    capability="verify_readback",
                    action_type=ActionTypeEnum.GET_FIELD_VALUES.value,
                    target_surface="browser_tab",
                    target_scope="active_context",
                    preconditions=["Observation available"],
                    expected_postconditions=["Verification result recorded in Evidence Ledger"],
                    requires_human_approval=False,
                ),
            ]

        return StructuredTaskPlan(
            plan_id=f"plan-local-{uuid4().hex[:8]}",
            task_goal=task.goal,
            workflow_mode=str(task.taskType),
            steps=steps,
            source_facts=source_facts,
            stop_conditions=["Task completed", "User cancelled", "Precondition mismatch"],
            model_provider="local_deterministic_planner",
            model_id="sahaay-local-v1",
            validation_status="LOCAL_FALLBACK",
        )



# Global singleton instance
muse_spark_open = MuseSparkOpenPlanner()
