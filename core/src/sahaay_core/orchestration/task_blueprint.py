"""Task Blueprint and Definition-of-Done Engine for Sahaay.

Structures every incoming natural-language goal into a validated, actionable execution contract
with explicit deliverables, constraints, risk gates, and acceptance verification criteria.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from sahaay_core.config.settings import settings
from sahaay_core.storage.persistence import durable_storage

logger = logging.getLogger(__name__)


class TaskBlueprint(BaseModel):
    """Authoritative execution blueprint for a Sahaay task."""

    taskId: str
    sessionId: str
    originalGoal: str
    normalizedOutcome: str
    constraints: List[str] = Field(default_factory=list)
    definitionOfDone: List[str] = Field(default_factory=list)
    deliverables: List[Dict[str, Any]] = Field(default_factory=list)
    requiredCapabilities: List[str] = Field(default_factory=list)
    informationRequired: List[str] = Field(default_factory=list)
    riskGates: List[str] = Field(default_factory=list)
    verificationCriteria: List[str] = Field(default_factory=list)
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TaskBlueprintService:
    """Creates, evaluates, and persists Task Blueprints."""

    @staticmethod
    def create_blueprint(
        task_id: str,
        session_id: str,
        goal: str,
        context: Optional[str] = None,
    ) -> TaskBlueprint:
        """Constructs a structured blueprint analyzing the goal and determining definition-of-done."""
        goal_lower = goal.lower()

        # Deterministic capability and deliverable inferencing
        normalized_outcome = goal.strip()
        constraints = [
            "Never bypass user consent or privacy gateways",
            "Use least privilege native tool operations",
            "Independent verification required before marking task completed",
        ]
        definition_of_done = []
        deliverables = []
        required_caps = []
        risk_gates = []
        verification_criteria = []

        # 1. Browser Tasks
        if any(w in goal_lower for w in ["open", "browse", "web", "youtube", "amazon", "google", "website", "tab", "url", "search"]):
            required_caps.extend(["browser_open_tab", "browser_get_active_tab", "browser_navigate", "browser_search_in_tab"])
            definition_of_done.append("Target web page is successfully loaded and accessible in browser")
            verification_criteria.append("Actual tab URL matches target domain or query parameter")

        # 2. Research & Investigation
        if any(w in goal_lower for w in ["research", "find", "investigate", "compare", "search for", "understand", "study"]):
            required_caps.extend(["research_web_multihop", "document_search_knowledge", "browser_tab_observe"])
            definition_of_done.append("Multi-source facts gathered with provenance URLs and citations")
            definition_of_done.append("Key findings and comparison synthesized with source citations")
            deliverables.append({"type": "research_synthesis", "format": "markdown"})
            verification_criteria.append("Synthesized findings contain at least one verifiable citation reference")

        # 3. Document Ingestion & Cross-Document Analysis
        if any(w in goal_lower for w in ["document", "file", "analyze", "inconsistenc", "pdf", "docx", "xlsx", "invoice", "report", "audit"]):
            required_caps.extend(["document_ingest_file", "document_search_knowledge", "document_compare_sources", "data_analyze_tabular"])
            definition_of_done.append("Target files ingested, parsed, and hashed via SHA-256")
            definition_of_done.append("Cross-document consistency and data analysis completed")
            verification_criteria.append("Context facts recorded in durable store with valid sourceReferenceId")

        # 4. Windows Desktop Operations
        if any(w in goal_lower for w in ["screen", "look at", "windows", "desktop", "notepad", "calculator", "calc", "app", "type", "click"]):
            required_caps.extend(["windows_launch_app", "windows_get_active_window", "windows_capture_screen", "windows_type_text", "windows_enumerate_controls"])
            definition_of_done.append("Target application window or control discovered and active")
            definition_of_done.append("Requested text entry, click, or screen analysis executed")
            verification_criteria.append("Window handle (HWND) > 0 verified and readback confirms state change")

        # 5. Artifact Creation
        if any(w in goal_lower for w in ["create", "write", "save", "generate", "prepare", "export", "report", "summary", "desktop"]):
            required_caps.extend(["file_create_write", "artifact_generate_document", "artifact_generate_spreadsheet"])
            deliverables.append({"type": "file_artifact", "format": "text_or_docx_or_xlsx", "location": "user_workspace_or_desktop"})
            definition_of_done.append("Deliverable artifact written to disk with SHA-256 fingerprint")
            verification_criteria.append("File exists on disk, file size > 0, readback matches expected content")

        # Ensure base definition of done
        if not definition_of_done:
            definition_of_done.append("User goal addressed with grounded observations and clear outcome")
            verification_criteria.append("Execution steps succeeded without fatal exceptions")

        blueprint = TaskBlueprint(
            taskId=task_id,
            sessionId=session_id,
            originalGoal=goal,
            normalizedOutcome=normalized_outcome,
            constraints=constraints,
            definitionOfDone=definition_of_done,
            deliverables=deliverables,
            requiredCapabilities=list(dict.fromkeys(required_caps)),
            informationRequired=[],
            riskGates=risk_gates,
            verificationCriteria=verification_criteria,
        )

        # Persist to durable storage
        try:
            durable_storage.save_task_blueprint(task_id, blueprint.to_dict())
            durable_storage.record_task_event(
                task_id=task_id,
                event_type="task.plan_created",
                stage="PLANNING",
                message=f"Constructed Task Blueprint with {len(definition_of_done)} definition-of-done criteria.",
                data=blueprint.to_dict(),
            )
        except Exception as ex:
            logger.warning("Could not persist task blueprint: %s", ex)

        return blueprint


task_blueprint_service = TaskBlueprintService()

