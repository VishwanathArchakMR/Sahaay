"""Mission Strategist and Strategic Task Planning Engine for Sahaay.

Uses Meta Muse Spark (and escalates to Muse Wonder when required) to formulate
structured Mission Strategies, classify task depth, establish concrete
Definitions of Done, and guide multi-phase tool execution.
"""

import json
import logging
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from sahaay_core.config.settings import settings
from sahaay_core.models.meta.muse_spark import MuseSparkClient
from sahaay_core.models.meta.muse_wonder import MuseWonderClient
from sahaay_core.orchestration.task_blueprint import TaskBlueprintService
from sahaay_core.storage.persistence import durable_storage

logger = logging.getLogger("sahaay.orchestration.mission_strategist")


class MissionPhase(BaseModel):
    """An individual phase within a multi-step mission."""

    phase_index: int
    name: str
    description: str
    required_capabilities: List[str] = Field(default_factory=list)
    expected_deliverable: Optional[str] = None


class MissionStrategy(BaseModel):
    """Authoritative structured strategy formulating the plan and definition of done."""

    strategy_id: str = Field(default_factory=lambda: f"strat-{uuid4()}")
    task_id: str
    session_id: str
    original_objective: str
    interpreted_objective: str
    depth_classification: Literal["DIRECT_OPERATION", "STRUCTURED_TASK", "COMPLEX_MISSION"]
    definition_of_done: List[str] = Field(default_factory=list)
    available_context: Optional[str] = None
    required_information: List[str] = Field(default_factory=list)
    execution_approach: str = ""
    execution_phases: List[MissionPhase] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    expected_deliverables: List[str] = Field(default_factory=list)
    verification_criteria: List[str] = Field(default_factory=list)
    failure_alternatives: List[str] = Field(default_factory=list)

    def format_for_execution_prompt(self) -> str:
        """Format the strategy into a high-density directive prompt for the ReAct loop."""
        lines = [
            "==================================================",
            "STRATEGIC MISSION PLAN & DEFINITION OF DONE",
            "==================================================",
            f"Primary Mission: {self.interpreted_objective}",
            f"Depth Level: {self.depth_classification}",
            f"Execution Approach: {self.execution_approach}",
            "",
            "EXECUTION PHASES:",
        ]
        for p in self.execution_phases:
            caps = ", ".join(p.required_capabilities) if p.required_capabilities else "any"
            lines.append(f"  Phase {p.phase_index}: {p.name}")
            lines.append(f"    - Directive: {p.description}")
            lines.append(f"    - Capabilities: [{caps}]")
            if p.expected_deliverable:
                lines.append(f"    - Deliverable: {p.expected_deliverable}")

        lines.extend([
            "",
            "DEFINITION OF DONE (Acceptance Criteria):",
        ])
        for dod in self.definition_of_done:
            lines.append(f"  [ ] {dod}")

        lines.extend([
            "",
            "INDEPENDENT VERIFICATION CRITERIA:",
        ])
        for vc in self.verification_criteria:
            lines.append(f"  * {vc}")

        if self.failure_alternatives:
            lines.extend([
                "",
                "RECOVERY & FALLBACK ALTERNATIVES:",
            ])
            for alt in self.failure_alternatives:
                lines.append(f"  * {alt}")

        lines.append("==================================================")
        return "\n".join(lines)


class MissionStrategist:
    """Strategic orchestrator for deep mission planning and model-driven execution."""

    def __init__(
        self,
        muse_spark: Optional[MuseSparkClient] = None,
        muse_wonder: Optional[MuseWonderClient] = None,
    ) -> None:
        self.spark = muse_spark or MuseSparkClient()
        self.wonder = muse_wonder or MuseWonderClient()

    async def analyze_objective(
        self,
        task_id: str,
        session_id: str,
        goal: str,
        context: Optional[str] = None,
        active_grants: Optional[List[Any]] = None,
        allow_model_call: bool = True,
        persist: bool = True,
    ) -> MissionStrategy:
        """Analyze user goal, formulate mission strategy, and establish Definition of Done."""
        goal_lower = goal.lower().strip()

        # Classify task depth
        depth: Literal["DIRECT_OPERATION", "STRUCTURED_TASK", "COMPLEX_MISSION"]
        compound_indicators = [
            " and ", " then ", " after that ", "compare", "analyze", "synthesize",
            "report", "spreadsheet", "generate document", "extract and", "research",
            "find out", "multi-step", "audit", "verify and"
        ]
        if any(ci in goal_lower for ci in compound_indicators):
            if any(ci in goal_lower for ci in ["report", "audit", "spreadsheet", "compare", "synthesize", "research"]):
                depth = "COMPLEX_MISSION"
            else:
                depth = "STRUCTURED_TASK"
        else:
            depth = "DIRECT_OPERATION"

        # Baseline deterministic blueprint
        bp = TaskBlueprintService.create_blueprint(
            task_id=task_id,
            session_id=session_id,
            goal=goal,
            context=context,
            persist=persist,
        )

        strategy_phases: List[MissionPhase] = []
        interpreted_objective = goal
        execution_approach = ""
        definition_of_done = list(bp.definitionOfDone)
        verification_criteria = list(bp.verificationCriteria)
        required_caps = list(bp.requiredCapabilities)
        deliverables = [str(d.get("type", "result")) for d in bp.deliverables]
        failure_alternatives = [
            "If target window is not foregrounded, focus and re-verify HWND",
            "If web page element not found, retry with broader selector or inspect tab DOM",
            "If primary model call fails, fall back to native deterministic execution",
        ]

        # Use Muse Spark to enrich and formulate deep strategic plan if available and online
        import sys
        is_testing = getattr(settings, "is_testing", False) or "pytest" in sys.modules
        is_model_usable = (
            allow_model_call
            and not is_testing
            and self.spark.client.is_configured
            and not settings.local_only_mode
        )

        if is_model_usable and depth in ("STRUCTURED_TASK", "COMPLEX_MISSION"):
            prompt = (
                f"Analyze this user mission objective for an autonomous Windows computer agent:\n"
                f"OBJECTIVE: {goal}\n"
                f"CONTEXT: {context or 'None provided'}\n\n"
                f"Formulate a structured mission strategy with:\n"
                f"1. interpreted_objective (clear distilled mission statement)\n"
                f"2. depth_classification ('STRUCTURED_TASK' or 'COMPLEX_MISSION')\n"
                f"3. execution_approach (2-3 sentences explaining the strategy)\n"
                f"4. execution_phases (array of 2-4 phases: phase_index, name, description, required_capabilities, expected_deliverable)\n"
                f"5. definition_of_done (array of 3-5 concrete measurable requirements)\n"
                f"6. verification_criteria (array of 2-4 independent verification tests)\n"
                f"7. failure_alternatives (array of 1-3 contingency actions if a step fails)\n\n"
                f"Respond ONLY with a valid JSON object matching these exact keys."
            )
            try:
                raw_resp = await self.spark.client.post_endpoint(
                    "chat/completions",
                    {
                        "model": self.spark.model_id,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are Sahaay Mission Strategist. You break complex computer and web missions "
                                    "into rigorous, phased execution strategies with strict Definitions of Done. "
                                    "Output valid JSON only."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                    },
                )
                choices = raw_resp.get("choices", [])
                if choices:
                    content_str = choices[0].get("message", {}).get("content", "")
                    # Extract JSON block if wrapped in markdown
                    if "```json" in content_str:
                        content_str = content_str.split("```json")[1].split("```")[0].strip()
                    elif "```" in content_str:
                        content_str = content_str.split("```")[1].split("```")[0].strip()

                    parsed = json.loads(content_str)
                    interpreted_objective = parsed.get("interpreted_objective", goal)
                    execution_approach = parsed.get("execution_approach", "")
                    if parsed.get("depth_classification") in ("STRUCTURED_TASK", "COMPLEX_MISSION"):
                        depth = parsed["depth_classification"]
                    if parsed.get("definition_of_done"):
                        definition_of_done = parsed["definition_of_done"]
                    if parsed.get("verification_criteria"):
                        verification_criteria = parsed["verification_criteria"]
                    if parsed.get("failure_alternatives"):
                        failure_alternatives = parsed["failure_alternatives"]

                    raw_phases = parsed.get("execution_phases", [])
                    for idx, ph in enumerate(raw_phases, 1):
                        strategy_phases.append(
                            MissionPhase(
                                phase_index=ph.get("phase_index", idx),
                                name=ph.get("name", f"Phase {idx}"),
                                description=ph.get("description", ""),
                                required_capabilities=ph.get("required_capabilities", []),
                                expected_deliverable=ph.get("expected_deliverable"),
                            )
                        )
            except Exception as ex:
                logger.warning("Muse Spark strategic analysis failed, using deterministic blueprint: %s", ex)

        # Fallback to deterministic phases if model was not used or failed
        if not strategy_phases:
            if depth == "DIRECT_OPERATION":
                strategy_phases.append(
                    MissionPhase(
                        phase_index=1,
                        name="Direct Execution & Verification",
                        description=f"Execute direct operation for '{goal}' and verify postcondition.",
                        required_capabilities=required_caps,
                        expected_deliverable="Target state achieved and verified",
                    )
                )
                execution_approach = f"Execute direct single-step capability and confirm completion."
            else:
                strategy_phases.append(
                    MissionPhase(
                        phase_index=1,
                        name="Environment Perception & Discovery",
                        description="Observe active browser tab or desktop application state and extract initial context.",
                        required_capabilities=["browser_get_active_tab", "windows_inspect_window", "browser_tab_observe"],
                        expected_deliverable="Current workspace state observed and logged",
                    )
                )
                strategy_phases.append(
                    MissionPhase(
                        phase_index=2,
                        name="Autonomous Action & Execution",
                        description=f"Execute required operations to fulfill objective: {goal}",
                        required_capabilities=required_caps or ["generic_capability_action"],
                        expected_deliverable="Core task operations applied",
                    )
                )
                strategy_phases.append(
                    MissionPhase(
                        phase_index=3,
                        name="Independent Verification & Artifact Finalization",
                        description="Read back resulting state, generate any requested artifacts, and confirm postcondition.",
                        required_capabilities=["file_create_write", "artifact_generate_document", "verify_readback"],
                        expected_deliverable="Deliverables recorded and verified",
                    )
                )
                execution_approach = (
                    "Perceive target application or web surface, execute necessary multi-step operations, "
                    "and independently verify results before marking task complete."
                )

        strategy = MissionStrategy(
            task_id=task_id,
            session_id=session_id,
            original_objective=goal,
            interpreted_objective=interpreted_objective,
            depth_classification=depth,
            definition_of_done=definition_of_done or ["Task objective fulfilled and verified."],
            available_context=context,
            required_information=["Current application/tab state", "User target parameters"],
            execution_approach=execution_approach,
            execution_phases=strategy_phases,
            required_capabilities=required_caps,
            dependencies=[],
            expected_deliverables=deliverables or ["Verified task result"],
            verification_criteria=verification_criteria or ["State transition confirmed by readback or telemetry."],
            failure_alternatives=failure_alternatives,
        )

        # Persist strategy events in durable SQLite store if task exists and persist is requested
        if persist:
            try:
                durable_storage.record_task_event(
                    task_id=task_id,
                    event_type="mission.strategy_formulated",
                    stage="PLANNING",
                    message=f"Mission Strategy: [{strategy.depth_classification}] {strategy.interpreted_objective}",
                    data={
                        "strategyId": strategy.strategy_id,
                        "depth": strategy.depth_classification,
                        "approach": strategy.execution_approach,
                        "phasesCount": len(strategy.execution_phases),
                        "definitionOfDone": strategy.definition_of_done,
                    },
                )
            except Exception as ex:
                logger.debug("Could not record mission strategy event to SQLite: %s", ex)

        return strategy

    async def escalate_to_visual_wonder(
        self,
        task_id: str,
        goal: str,
        screenshot_bytes: bytes,
        target_surface: Literal["browser_tab", "windows_app", "desktop"] = "desktop",
        active_grants: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Escalate to Muse Wonder computer-use model for visual reasoning on obstacle or complex UI."""
        logger.info("Escalating task %s to Muse Wonder for visual computer use reasoning", task_id)
        durable_storage.record_task_event(
            task_id=task_id,
            event_type="mission.wonder_escalation",
            stage="EXECUTING",
            message=f"Escalating obstacle to Muse Wonder for visual reasoning ({target_surface})",
            data={"goal": goal, "surface": target_surface},
        )
        try:
            proposal = await self.wonder.propose_computer_action(
                task_id=task_id,
                goal=goal,
                screenshot_bytes=screenshot_bytes,
                target_surface=target_surface,
                active_grants=active_grants or [],
            )
            return {
                "success": True,
                "proposalId": proposal.proposal_id,
                "toolCalls": [tc.model_dump() for tc in proposal.proposed_tool_calls],
                "isSafe": proposal.is_safe,
                "safetyNotes": proposal.safety_notes,
            }
        except Exception as ex:
            logger.warning("Muse Wonder visual escalation encountered error: %s", ex)
            return {"success": False, "error": str(ex)}


mission_strategist = MissionStrategist()
