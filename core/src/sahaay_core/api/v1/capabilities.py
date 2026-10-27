"""Capabilities Endpoint for Sahaay Core Backend."""

from fastapi import APIRouter

from sahaay_core.contracts.models import CapabilityDescriptor

router = APIRouter(tags=["Capabilities"])


@router.get("/capabilities", response_model=CapabilityDescriptor)
async def get_capabilities() -> CapabilityDescriptor:
    """Report capabilities truthfully: only what is genuinely available in this build stage.

    Desktop Automation, Browser Automation, and External Models are marked FALSE/EMPTY.
    """
    return CapabilityDescriptor(
        systemVersion="0.1.0-foundation",
        desktopAutomationAvailable=False,
        browserAutomationAvailable=False,
        modelsAvailable=[],  # No live models connected in Stage 01
        activeCapabilities=[
            "session_management",
            "consent_grant_lifecycle",
            "task_state_machine",
            "action_gate_authorization",
            "privacy_gateway_fail_closed",
            "provenance_context_store",
            "source_authorization_and_revocation",
            "independent_verification_engine",
            "evidence_ledger",
        ],
    )
