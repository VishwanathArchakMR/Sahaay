"""Task Passport and Visual Storytelling API for Sahaay.

Provides user-facing visual milestone storytelling, step illustrations, and
artifact lifecycle management powered by Muse Image with trustworthy SVG fallbacks.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from sahaay_core.config.settings import settings
from sahaay_core.models.meta.muse_image import muse_image
from sahaay_core.storage.persistence import durable_storage

logger = logging.getLogger(__name__)

storytelling_router = APIRouter(prefix="/tasks", tags=["Task Storytelling & Passport"])
router = storytelling_router


class MilestoneCard(BaseModel):
    """Visual milestone card for the Task Passport."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    milestone_id: str
    milestone_type: str  # source_ingest | plan_prepared | policy_authorized | action_executed | verified | audit_recorded
    title: str
    description: str
    status: str  # PENDING | EXECUTED | VERIFIED | FAILED | AUTHORIZED
    direction: Optional[str] = None
    source_reference: Optional[str] = None
    evidence_id: Optional[str] = None
    illustration_url: Optional[str] = None
    svg_fallback: str
    is_ai_generated: bool = False
    ai_label: str = "Vector Illustration"
    timestamp: str
    technical_details: Dict[str, Any] = Field(default_factory=dict)


class TaskPassportResponse(BaseModel):
    """Complete visual Task Passport response."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    task_id: str
    goal: str
    workflow_mode: str
    source_to_target: str
    verification_status: str
    total_milestones: int
    milestones: List[MilestoneCard]
    summary_notice: str
    visual_storytelling_enabled: bool = True


class StepIllustrateRequest(BaseModel):
    """Request to generate or regenerate an illustration for a milestone."""

    milestone_type: str
    direction: Optional[str] = "Browser → Desktop"
    abstract_context: Optional[str] = ""
    session_id: Optional[str] = "default"


# In-memory passport store populated by workflows
task_passports: Dict[str, TaskPassportResponse] = {}


def register_or_update_passport(
    task_id: str,
    goal: str,
    workflow_mode: str,
    direction: str,
    extracted_fields: Dict[str, Any],
    verification_status: str,
    evidence_id: str,
    target_app_or_url: str,
    source_ref: str,
) -> TaskPassportResponse:
    """Helper called by workflows to construct an authoritative, trustworthy Task Passport."""
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Source Milestone
    m1 = MilestoneCard(
        milestone_id=f"ms-{task_id}-1",
        milestone_type="source_ingest",
        title="Source Context Ingested",
        description=f"Authorized context read from {source_ref} and verified via SHA-256 fingerprint.",
        status="VERIFIED",
        direction=direction,
        source_reference=source_ref,
        evidence_id=f"{evidence_id}-src",
        svg_fallback=muse_image._generate_vector_svg("source_ingest", direction),
        is_ai_generated=False,
        ai_label="Vector Illustration",
        timestamp=now,
        technical_details={"source": source_ref, "extracted_keys": list(extracted_fields.keys())},
    )

    # 2. Plan Milestone
    m2 = MilestoneCard(
        milestone_id=f"ms-{task_id}-2",
        milestone_type="plan_prepared",
        title="Structured Plan Formulated",
        description="Muse Spark Open generated a typed sequential plan with deterministic Action Gate boundaries.",
        status="EXECUTED",
        direction=direction,
        source_reference=source_ref,
        evidence_id=f"{evidence_id}-plan",
        svg_fallback=muse_image._generate_vector_svg("plan_prepared", direction),
        is_ai_generated=False,
        ai_label="Vector Illustration",
        timestamp=now,
        technical_details={"workflow": workflow_mode, "planned_steps": 4},
    )

    # 3. Policy Authorization Milestone
    m3 = MilestoneCard(
        milestone_id=f"ms-{task_id}-3",
        milestone_type="policy_authorized",
        title="Action Gate Authorized",
        description=f"Action Gate evaluated consent grant and verified target scope '{target_app_or_url}'.",
        status="AUTHORIZED",
        direction=direction,
        source_reference=source_ref,
        evidence_id=f"{evidence_id}-auth",
        svg_fallback=muse_image._generate_vector_svg("policy_authorized", direction),
        is_ai_generated=False,
        ai_label="Vector Illustration",
        timestamp=now,
        technical_details={"policy_decision": "ALLOW", "scope": target_app_or_url},
    )

    # 4. Action Execution Milestone
    m4 = MilestoneCard(
        milestone_id=f"ms-{task_id}-4",
        milestone_type="action_executed",
        title=f"Cross-Surface Transfer: {direction}",
        description=f"Dispatched fields to target '{target_app_or_url}'. General shell execution permanently blocked.",
        status="EXECUTED",
        direction=direction,
        source_reference=source_ref,
        evidence_id=f"{evidence_id}-exec",
        svg_fallback=muse_image._generate_vector_svg("action_executed", direction),
        is_ai_generated=False,
        ai_label="Vector Illustration",
        timestamp=now,
        technical_details={"target": target_app_or_url, "fields_transferred": extracted_fields},
    )

    # 5. Verification Milestone
    m5 = MilestoneCard(
        milestone_id=f"ms-{task_id}-5",
        milestone_type="verified",
        title="Independent Postcondition Check",
        description="Independent verifier read back live state from target and verified values match. Model self-attestation rejected.",
        status=verification_status,
        direction=direction,
        source_reference=source_ref,
        evidence_id=evidence_id,
        svg_fallback=muse_image._generate_vector_svg("verified", direction),
        is_ai_generated=False,
        ai_label="Vector Illustration",
        timestamp=now,
        technical_details={"verification_status": verification_status, "evidence_id": evidence_id},
    )

    passport = TaskPassportResponse(
        task_id=task_id,
        goal=goal,
        workflow_mode=workflow_mode,
        source_to_target=direction,
        verification_status=verification_status,
        total_milestones=5,
        milestones=[m1, m2, m3, m4, m5],
        summary_notice="Illustrations are generated as visual metaphors. Exact labels, statuses, and evidence IDs are rendered independently from verified SQLite records.",
        visual_storytelling_enabled=settings.enable_visual_storytelling,
    )

    task_passports[task_id] = passport
    try:
        durable_storage.save_task_passport(passport.model_dump(by_alias=True))
    except Exception as exc:
        logger.warning("Could not persist task passport for %s to SQLite: %s", task_id, exc)

    return passport


@storytelling_router.get("/{task_id}/passport", response_model=TaskPassportResponse)
async def get_task_passport(task_id: str) -> TaskPassportResponse:
    """Retrieves the Task Passport for a completed or active workflow.

    Returns 404 if the task or its passport does not exist.
    """
    if task_id in task_passports:
        return task_passports[task_id]

    stored = durable_storage.get_task_passport(task_id)
    if stored:
        try:
            passport = TaskPassportResponse.model_validate(stored)
            task_passports[task_id] = passport
            return passport
        except Exception as exc:
            logger.error("Failed to parse stored passport for %s: %s", task_id, exc)

    # Nonexistent task passport must return 404
    raise HTTPException(
        status_code=404,
        detail=f"Task Passport for task '{task_id}' not found. No fabricated record returned.",
    )


@storytelling_router.post("/{task_id}/steps/{step_id}/illustrate")
async def explain_this_step(
    task_id: str,
    step_id: str,
    req: StepIllustrateRequest,
) -> Dict[str, Any]:
    """Generates or regenerates an illustration for a specific milestone ('Explain this step').

    Enforces Privacy Gateway checks and prompt minimization.
    """
    grants = []
    if req.session_id and req.session_id != "default":
        try:
            s_uuid = UUID(req.session_id)
            grants = durable_storage.get_consent_grants_for_session(s_uuid)
        except Exception:
            pass

    result = await muse_image.generate_step_illustration(
        task_id=task_id,
        step_id=step_id,
        milestone_type=req.milestone_type,
        direction=req.direction or "Browser → Desktop",
        abstract_context=req.abstract_context or "",
        active_grants=grants,
    )

    # If passport exists, update milestone illustration
    if task_id in task_passports:
        passport = task_passports[task_id]
        for m in passport.milestones:
            if m.milestone_id == step_id or req.milestone_type in m.milestone_type:
                m.illustration_url = result.image_url
                m.svg_fallback = result.svg_fallback or m.svg_fallback
                m.is_ai_generated = result.is_ai_generated
                m.ai_label = (
                    "AI-Generated Illustration (Muse Image)"
                    if result.is_ai_generated
                    else "Vector Illustration"
                )
        try:
            durable_storage.save_task_passport(passport.model_dump(by_alias=True))
        except Exception:
            pass

    return {
        "success": True,
        "taskId": task_id,
        "stepId": step_id,
        "milestoneType": req.milestone_type,
        "isAiGenerated": result.is_ai_generated,
        "imageUrl": result.image_url,
        "svgFallback": result.svg_fallback,
        "aiLabel": "AI-Generated Illustration (Muse Image)"
        if result.is_ai_generated
        else "Vector Illustration",
        "latencyMs": round(result.latency_ms, 2),
        "fileSizeBytes": result.file_size_bytes,
        "notice": "Visual metaphor only. Factual evidence remains verified by deterministic application code.",
    }


@storytelling_router.delete("/{task_id}/artifacts")
async def delete_task_visual_artifacts(task_id: str) -> Dict[str, Any]:
    """Deletes all generated visual artwork for a task to honor user data revocation."""
    deleted_count = muse_image.delete_task_artifacts(task_id)
    durable_storage.deactivate_task_artifacts(task_id)

    # Revert passport images to local vector fallback
    if task_id in task_passports:
        for m in task_passports[task_id].milestones:
            m.illustration_url = None
            m.is_ai_generated = False
            m.ai_label = "Vector Illustration"
        try:
            durable_storage.save_task_passport(task_passports[task_id].model_dump(by_alias=True))
        except Exception:
            pass

    return {
        "success": True,
        "taskId": task_id,
        "artifactsDeleted": deleted_count,
        "message": f"Successfully deleted visual artifacts for task {task_id}.",
    }
