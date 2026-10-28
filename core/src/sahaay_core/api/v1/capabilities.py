"""Capabilities Endpoint for Sahaay Core Backend."""

from typing import List

from fastapi import APIRouter

from sahaay_core.adapters.windows.adapter import WindowsNativeAdapter
from sahaay_core.capabilities.models import CapabilityDescriptor as RegistryCapabilityDescriptor
from sahaay_core.capabilities.registry import capability_registry
from sahaay_core.contracts.models import CapabilityDescriptor

router = APIRouter(tags=["Capabilities"])
windows_adapter = WindowsNativeAdapter()


@router.get("/capabilities", response_model=CapabilityDescriptor)
async def get_capabilities() -> CapabilityDescriptor:
    """Report capabilities truthfully: check live connection to companion daemon.

    Desktop Automation is True if Sahaay.Controller named pipe responds.
    Browser Automation is True (Manifest V3 bridge available).
    External Models remain empty/disabled in this stage unless authorized.
    """
    is_companion_live = windows_adapter.ping()

    # Base mechanism capabilities required by Stage 02 contract
    active_caps = [
        "session_management",
        "consent_grant_lifecycle",
        "task_state_machine",
        "action_gate_authorization",
        "privacy_gateway_fail_closed",
        "provenance_context_store",
        "source_authorization_and_revocation",
        "independent_verification_engine",
        "evidence_ledger",
        "browser_tab_observation",
        "browser_bounded_scroll_action",
        "deterministic_source_grounded_retrieval",
        "local_document_ingestion",
        "combined_retrieval_and_action",
    ]

    # Incorporate registered capabilities from authoritative registry
    for cap in capability_registry.list_capabilities():
        if cap.capability_id not in active_caps:
            active_caps.append(cap.capability_id)

    if is_companion_live:
        active_caps.extend(
            [
                "windows_window_discovery",
                "windows_ui_automation_inspection",
                "windows_controlled_screenshot_capture",
            ]
        )

    return CapabilityDescriptor(
        systemVersion="0.6.0-runtime-integrity",
        desktopAutomationAvailable=is_companion_live,
        browserAutomationAvailable=True,
        modelsAvailable=[],
        activeCapabilities=active_caps,
    )


@router.get("/capabilities/registry", response_model=List[RegistryCapabilityDescriptor])
async def list_registry_capabilities() -> List[RegistryCapabilityDescriptor]:
    """List detailed capability descriptors from the authoritative registry."""
    return capability_registry.list_capabilities()
