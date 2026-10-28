"""Central Authoritative Capability Registry for Sahaay.

Maintains the single source of truth for all implemented system capabilities,
backing Muse Spark Open planning, Action Gate policy evaluation, and API discovery.
"""

import logging
from typing import Dict, List, Optional, Tuple

from sahaay_core.capabilities.models import (
    CapabilityDescriptor,
    CapabilityReadiness,
    RiskCategory,
)

logger = logging.getLogger(__name__)


class CapabilityRegistry:
    """Central registry of executable capabilities in the Sahaay platform."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, CapabilityDescriptor] = {}
        self._register_default_capabilities()

    def register(self, descriptor: CapabilityDescriptor) -> None:
        """Register or update a capability descriptor."""
        self._capabilities[descriptor.capability_id] = descriptor
        logger.debug("Registered capability: %s", descriptor.capability_id)

    def get(self, capability_id: str) -> Optional[CapabilityDescriptor]:
        """Fetch a capability descriptor by ID."""
        return self._capabilities.get(capability_id)

    def is_registered(self, capability_id: str) -> bool:
        """Check if capability exists in the registry."""
        return capability_id in self._capabilities

    def list_capabilities(self) -> List[CapabilityDescriptor]:
        """List all registered capabilities."""
        return list(self._capabilities.values())

    def get_catalog_for_prompt(self) -> str:
        """Serializes capabilities into a concise prompt string for planning models."""
        catalog_lines = []
        for cap in self._capabilities.values():
            catalog_lines.append(
                f"- ID: {cap.capability_id} ({cap.name})\n"
                f"  Surfaces: {', '.join(cap.supported_surfaces)}\n"
                f"  Description: {cap.description}\n"
                f"  Risk: {cap.risk_category.value} | Human confirmation: {cap.requires_human_confirmation}\n"
                f"  Verification: {cap.verification_method}"
            )
        return "\n".join(catalog_lines)

    def validate_plan_step(
        self, capability_id: str, parameters: Dict
    ) -> Tuple[bool, Optional[str]]:
        """Validate an individual proposed step against the registry."""
        cap = self.get(capability_id)
        if not cap:
            return False, f"Capability '{capability_id}' is not registered in the system."
        if cap.readiness_state == CapabilityReadiness.UNAVAILABLE:
            return False, f"Capability '{capability_id}' is currently UNAVAILABLE."
        return True, None

    def _register_default_capabilities(self) -> None:
        """Register capabilities implemented in Sahaay."""
        # 1. Browser Observation
        self.register(
            CapabilityDescriptor(
                capability_id="browser_tab_observe",
                name="Observe Browser Tab",
                description="Extract text, DOM content, and metadata from authorized browser tab.",
                example_requests=[
                    "Extract electricity bill details from active tab",
                    "Read account balance",
                ],
                supported_surfaces=["browser_tab"],
                adapter="browser_extension_bridge",
                input_schema={"type": "object", "properties": {"tabId": {"type": "integer"}}},
                output_schema={
                    "type": "object",
                    "properties": {"pageText": {"type": "string"}, "url": {"type": "string"}},
                },
                preconditions=["Browser extension connected", "Tab URL is within permitted scope"],
                required_permission_scopes=["read:browser_tab"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Cryptographic SHA-256 fingerprinting of retrieved DOM text.",
                required_postconditions=["Non-empty DOM text with valid hash"],
                readiness_state=CapabilityReadiness.READY,
                known_limitations=["Cannot read password inputs or cross-origin restricted frames"],
            )
        )

        # 2. Browser Form Fill
        self.register(
            CapabilityDescriptor(
                capability_id="browser_fill_form",
                name="Fill Browser Form Fields",
                description="Populate specific input fields on an authorized web page without automatic submission.",
                example_requests=["Populate bill amount and account number in payment form"],
                supported_surfaces=["browser_tab"],
                adapter="browser_extension_bridge",
                input_schema={
                    "type": "object",
                    "properties": {"fields": {"type": "object"}},
                    "required": ["fields"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"filledCount": {"type": "integer"}},
                },
                preconditions=[
                    "Target form inputs exist on active tab",
                    "Explicit consent granted",
                ],
                required_permission_scopes=["write:browser_form"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=True,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Independent readback via get_field_values comparing DOM values against source facts.",
                required_postconditions=["Target DOM elements contain exact expected values"],
                readiness_state=CapabilityReadiness.READY,
                known_limitations=[
                    "Automatic form submission is prohibited; requires human user click"
                ],
            )
        )

        # 3. Browser Readback Values
        self.register(
            CapabilityDescriptor(
                capability_id="browser_get_values",
                name="Read Browser Form Values",
                description="Inspect live values of input fields in the active browser tab.",
                example_requests=["Read back current values in payment form"],
                supported_surfaces=["browser_tab"],
                adapter="browser_extension_bridge",
                input_schema={"type": "object", "properties": {"fieldNames": {"type": "array"}}},
                output_schema={"type": "object", "properties": {"values": {"type": "object"}}},
                preconditions=["Active tab exists and is accessible"],
                required_permission_scopes=["read:browser_tab"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Direct inspection of DOM value properties.",
                required_postconditions=["Field values returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 4. Windows Control Text
        self.register(
            CapabilityDescriptor(
                capability_id="windows_set_control_text",
                name="Set Windows Control Text",
                description="Write text into an authorized control within an open Windows desktop window via UIA.",
                example_requests=[
                    "Write invoice summary into Notepad",
                    "Paste accounting data into desktop target",
                ],
                supported_surfaces=["desktop_window"],
                adapter="windows_native_companion",
                input_schema={
                    "type": "object",
                    "properties": {"hwnd": {"type": "integer"}, "text": {"type": "string"}},
                    "required": ["hwnd", "text"],
                },
                output_schema={"type": "object", "properties": {"writtenText": {"type": "string"}}},
                preconditions=[
                    "Target window handle > 0 exists",
                    "Window is not elevated/protected",
                    "Consent granted",
                ],
                required_permission_scopes=["write:desktop_window"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=True,
                is_reversible=True,
                potential_side_effects=["Modifies target document/editor buffer"],
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Independent readback of control text via UIA ValuePattern/TextPattern.",
                required_postconditions=["Actual readback text matches extracted source facts"],
                readiness_state=CapabilityReadiness.READY,
                known_limitations=["Does not support elevated admin windows or raw key injection"],
            )
        )

        # 5. Windows Inspect Control
        self.register(
            CapabilityDescriptor(
                capability_id="windows_get_control_text",
                name="Read Windows Control Text",
                description="Read live text from an authorized desktop window control via UI Automation.",
                example_requests=["Read text from active Notepad window"],
                supported_surfaces=["desktop_window"],
                adapter="windows_native_companion",
                input_schema={
                    "type": "object",
                    "properties": {"hwnd": {"type": "integer"}},
                    "required": ["hwnd"],
                },
                output_schema={"type": "object", "properties": {"text": {"type": "string"}}},
                preconditions=["Target window handle > 0 exists"],
                required_permission_scopes=["read:desktop_window"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="UIA readback inspection.",
                required_postconditions=["Text returned from control"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 6. Windows Window Listing / Bounds
        self.register(
            CapabilityDescriptor(
                capability_id="windows_inspect_window",
                name="Inspect Desktop Windows",
                description="Enumerate top-level open application windows and obtain bounding rectangles.",
                example_requests=["List open windows to identify destination application"],
                supported_surfaces=["desktop_window"],
                adapter="windows_native_companion",
                input_schema={"type": "object"},
                output_schema={"type": "object", "properties": {"windows": {"type": "array"}}},
                preconditions=["Companion service running"],
                required_permission_scopes=["read:desktop_window"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=3.0,
                is_idempotent=True,
                verification_method="Windows EnumWindows API confirmation.",
                required_postconditions=["List of valid hwnd handles returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 7. Document Ingestion
        self.register(
            CapabilityDescriptor(
                capability_id="document_ingest_chunk",
                name="Ingest Local Document",
                description="Read and chunk an authorized local file (text, JSON, PDF) within permitted folder.",
                example_requests=["Load bill details from local invoice document"],
                supported_surfaces=["local_store"],
                adapter="local_document_adapter",
                input_schema={
                    "type": "object",
                    "properties": {"filePath": {"type": "string"}},
                    "required": ["filePath"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"content": {"type": "string"}, "sha256": {"type": "string"}},
                },
                preconditions=[
                    "File path is within authorized workspace/data path",
                    "File size <= 10MB",
                ],
                required_permission_scopes=["read:local_file"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="SHA-256 fingerprint verification against source reference record.",
                required_postconditions=["File read and fingerprint recorded in source registry"],
                readiness_state=CapabilityReadiness.READY,
                known_limitations=["Only UTF-8 text and structured JSON supported in base runtime"],
            )
        )

        # 8. Deterministic Retrieval
        self.register(
            CapabilityDescriptor(
                capability_id="deterministic_retrieval",
                name="Retrieve Grounded Facts",
                description="Query stored context facts strictly filtered by active, non-revoked sources.",
                example_requests=["Find invoice amount in ingested documents"],
                supported_surfaces=["local_store"],
                adapter="context_store_adapter",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                output_schema={"type": "array", "items": {"type": "object"}},
                preconditions=["ContextStore initialized"],
                required_permission_scopes=["read:context_facts"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=2.0,
                is_idempotent=True,
                verification_method="Exact keyword and provenance tree matching.",
                required_postconditions=["Only facts from active permitted sources returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 9. Independent Readback Verification
        self.register(
            CapabilityDescriptor(
                capability_id="verify_readback",
                name="Verify Target State",
                description="Independently inspect destination surface to verify execution matched expected postconditions.",
                example_requests=["Verify desktop text contains transferred bill amount"],
                supported_surfaces=["browser_tab", "desktop_window"],
                adapter="independent_verifier",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target": {"type": "string"},
                        "expectedFacts": {"type": "object"},
                    },
                },
                output_schema={"type": "object", "properties": {"isVerified": {"type": "boolean"}}},
                preconditions=["Action execution completed"],
                required_permission_scopes=["verify:postcondition"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Independent comparison by application code without model self-attestation.",
                required_postconditions=[
                    "Cryptographic evidence record generated in evidence ledger"
                ],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 10. User Authorization Handoff
        self.register(
            CapabilityDescriptor(
                capability_id="user_authorization",
                name="Request User Authorization",
                description="Explicitly halt task execution and request human consent for a specific high-risk action.",
                example_requests=["Prompt user to authorize writing to accounting application"],
                supported_surfaces=["local_store"],
                adapter="action_gate_handoff",
                input_schema={
                    "type": "object",
                    "properties": {"scope": {"type": "string"}, "purpose": {"type": "string"}},
                },
                output_schema={"type": "object", "properties": {"granted": {"type": "boolean"}}},
                preconditions=["Task in AUTHORIZING state"],
                required_permission_scopes=[],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=60.0,
                is_idempotent=False,
                verification_method="ConsentGrant verification in durable session store.",
                required_postconditions=[
                    "Explicit ConsentGrant saved in SQLite or task remains halted"
                ],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 11. Internet Web Search
        self.register(
            CapabilityDescriptor(
                capability_id="research_web_search",
                name="Public Internet Web Search",
                description="Submit public search queries to a keyless search provider, normalizing results and citations.",
                example_requests=["Search for BESCOM current electricity tariff rates"],
                supported_surfaces=["internet"],
                adapter="internet_research_adapter",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "maxResults": {"type": "integer"}},
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"results": {"type": "array"}, "citations": {"type": "array"}},
                },
                preconditions=[
                    "Internet access available",
                    "Local-only mode not blocking outbound research",
                ],
                required_permission_scopes=["internet:research"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=8.0,
                is_idempotent=True,
                verification_method="Result structure normalization and timestamped citation generation.",
                required_postconditions=["Clean source citations linked to retrieval records"],
                readiness_state=CapabilityReadiness.READY,
                known_limitations=[
                    "Public metasearch is best-effort; rate limits or provider changes report graceful unavailable state"
                ],
            )
        )

        # 12. Safe Web Page Fetcher
        self.register(
            CapabilityDescriptor(
                capability_id="research_fetch_page",
                name="Safe Web Page Retrieval",
                description="Retrieve public webpage content with strict SSRF defense (blocking private/internal IPs) and size limits.",
                example_requests=["Fetch official tariff document from electricity board website"],
                supported_surfaces=["internet"],
                adapter="safe_web_fetcher",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "extractedText": {"type": "string"},
                        "sha256": {"type": "string"},
                    },
                },
                preconditions=[
                    "Valid http/https URL",
                    "URL does not resolve to private, local, or cloud metadata IP",
                ],
                required_permission_scopes=["internet:research"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=10.0,
                is_idempotent=True,
                verification_method="SSRF validation, size/timeout enforcement, and SHA-256 source registration.",
                required_postconditions=[
                    "Page text safely extracted and registered in SourceManager with provenance hash"
                ],
                readiness_state=CapabilityReadiness.READY,
                known_limitations=[
                    "Blocks JavaScript execution, cookies, and authenticated sessions"
                ],
            )
        )

        # 13. Windows Launch Application
        self.register(
            CapabilityDescriptor(
                capability_id="windows_launch_app",
                name="Launch Windows Application",
                description="Launch an authorized native Windows desktop application from the strict allowlist (Notepad, Calculator, Explorer).",
                example_requests=["Open Calculator", "Open Notepad to write notes"],
                supported_surfaces=["desktop_window"],
                adapter="windows_native_companion",
                input_schema={
                    "type": "object",
                    "properties": {"application": {"type": "string"}},
                    "required": ["application"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "isLaunched": {"type": "boolean"},
                        "processName": {"type": "string"},
                        "processId": {"type": "integer"},
                        "hwnd": {"type": "integer"},
                        "windowTitle": {"type": "string"},
                    },
                },
                preconditions=["Companion service running", "Target app is in allowlist"],
                required_permission_scopes=["write:desktop_window"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Window discovery and process enumeration confirms application is running.",
                required_postconditions=["Target application window discovered and active"],
                readiness_state=CapabilityReadiness.READY,
                known_limitations=[
                    "Shell execution of arbitrary commands or scripts is strictly disabled"
                ],
            )
        )

        # 14. Windows Click Control
        self.register(
            CapabilityDescriptor(
                capability_id="windows_click_control",
                name="Click Windows Control",
                description="Invoke or click an accessible control in an authorized desktop window via UI Automation.",
                example_requests=["Click the Clear button in Calculator", "Click Save"],
                supported_surfaces=["desktop_window"],
                adapter="windows_native_companion",
                input_schema={
                    "type": "object",
                    "properties": {"hwnd": {"type": "integer"}, "targetId": {"type": "string"}},
                    "required": ["hwnd"],
                },
                output_schema={"type": "object", "properties": {"verified": {"type": "boolean"}}},
                preconditions=["Target window handle exists and is accessible"],
                required_permission_scopes=["write:desktop_window"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=False,
                is_reversible=False,
                timeout_seconds=5.0,
                is_idempotent=False,
                verification_method="UI Automation invoke pattern execution and post-click element state check.",
                required_postconditions=["Control invoked without error"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 15. Windows Set System Volume
        self.register(
            CapabilityDescriptor(
                capability_id="windows_set_volume",
                name="Set Windows System Volume",
                description="Adjust master system audio volume (0-100) using Windows Core Audio API, independently reading back actual level.",
                example_requests=["Set system volume to 60%", "Mute system audio"],
                supported_surfaces=["system_state"],
                adapter="windows_native_companion",
                input_schema={
                    "type": "object",
                    "properties": {"volume": {"type": "integer", "minimum": 0, "maximum": 100}},
                    "required": ["volume"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "volumePercent": {"type": "integer"},
                        "previousVolumePercent": {"type": "integer"},
                        "isMuted": {"type": "boolean"},
                    },
                },
                preconditions=["Windows Core Audio service active"],
                required_permission_scopes=["write:system_settings"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=3.0,
                is_idempotent=True,
                verification_method="Independent readback of master volume scalar via Core Audio endpoint.",
                required_postconditions=["Verified system volume matches target percentage"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 16. Windows Get System Volume
        self.register(
            CapabilityDescriptor(
                capability_id="windows_get_volume",
                name="Get Windows System Volume",
                description="Query current master system audio volume and mute status via Windows Core Audio API.",
                example_requests=["What is my current system volume?"],
                supported_surfaces=["system_state"],
                adapter="windows_native_companion",
                input_schema={"type": "object"},
                output_schema={
                    "type": "object",
                    "properties": {
                        "volumePercent": {"type": "integer"},
                        "isMuted": {"type": "boolean"},
                    },
                },
                preconditions=["Windows Core Audio service active"],
                required_permission_scopes=["read:system_settings"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=2.0,
                is_idempotent=True,
                verification_method="Direct inspection of Core Audio endpoint volume scalar.",
                required_postconditions=["System volume level returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 17. Browser Scroll Tab
        self.register(
            CapabilityDescriptor(
                capability_id="browser_scroll_tab",
                name="Scroll Browser Tab",
                description="Scroll the active browser tab vertically by a specified delta in pixels.",
                example_requests=["Scroll down 300px", "Scroll to next section"],
                supported_surfaces=["browser_tab"],
                adapter="browser_extension_bridge",
                input_schema={
                    "type": "object",
                    "properties": {"deltaY": {"type": "integer"}},
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "preScrollY": {"type": "integer"},
                        "postScrollY": {"type": "integer"},
                        "actualDeltaY": {"type": "integer"},
                    },
                },
                preconditions=["Active browser tab loaded"],
                required_permission_scopes=["action:browser_tab"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=3.0,
                is_idempotent=False,
                verification_method="Independent readback of scrollY before and after action.",
                required_postconditions=["postScrollY - preScrollY equals requested delta"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 18. Browser Click Element
        self.register(
            CapabilityDescriptor(
                capability_id="browser_click_element",
                name="Click Browser Element",
                description="Click an accessible interactive element on the active browser tab by target ID or selector.",
                example_requests=["Click submit button", "Click search icon"],
                supported_surfaces=["browser_tab"],
                adapter="browser_extension_bridge",
                input_schema={
                    "type": "object",
                    "properties": {"target": {"type": "string"}},
                    "required": ["target"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "clicked": {"type": "boolean"},
                        "target": {"type": "string"},
                    },
                },
                preconditions=["Active browser tab loaded", "Target element is visible and interactive"],
                required_permission_scopes=["action:browser_tab"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=False,
                is_reversible=False,
                timeout_seconds=4.0,
                is_idempotent=False,
                verification_method="Post-click element focus and DOM change observation.",
                required_postconditions=["Element clicked confirmed by content script"],
                readiness_state=CapabilityReadiness.READY,
            )
        )


# Global singleton instance
capability_registry = CapabilityRegistry()
