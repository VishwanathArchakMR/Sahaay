"""Central Authoritative Capability Registry for Sahaay.

Maintains the single source of truth for all implemented system capabilities,
backing Muse Spark Open planning, Action Gate policy evaluation, and API discovery.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

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

    def to_model_tool_definitions(
        self, filter_surfaces: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Serializes registered capabilities into OpenAI-compatible function calling tool definitions."""
        tools = []
        for cap in self._capabilities.values():
            if cap.readiness_state == CapabilityReadiness.UNAVAILABLE:
                continue
            if filter_surfaces and not any(s in filter_surfaces for s in cap.supported_surfaces):
                continue
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": cap.capability_id,
                        "description": cap.description,
                        "parameters": cap.input_schema or {"type": "object", "properties": {}},
                    },
                }
            )
        return tools

    def get_tool_definitions_for_task(
        self, goal: str, context: str = ""
    ) -> List[Dict[str, Any]]:
        """Dynamically provides all ready system tools for autonomous planning."""
        return self.to_model_tool_definitions()

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
                    "Extract key structured data from active tab",
                    "Read webpage summary",
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
                example_requests=["Search for latest developments in AI agents"],
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
                example_requests=["Fetch official documentation from research website"],
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
                preconditions=[
                    "Active browser tab loaded",
                    "Target element is visible and interactive",
                ],
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

        # 19. Browser Open Tab
        self.register(
            CapabilityDescriptor(
                capability_id="browser_open_tab",
                name="Open Browser Tab",
                description="Open a new browser tab at a specified URL and return the tab URL and title.",
                example_requests=["Open Amazon in my browser", "Open YouTube", "Navigate to google.com"],
                supported_surfaces=["browser_tab"],
                adapter="browser_extension_bridge",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}, "title": {"type": "string"}, "tabId": {"type": "integer"}},
                },
                preconditions=["Browser extension connected"],
                required_permission_scopes=["action:browser_tab"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=8.0,
                is_idempotent=True,
                verification_method="Actual tab URL and title returned from extension.",
                required_postconditions=["New tab opened at requested URL"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 20. Browser Navigate
        self.register(
            CapabilityDescriptor(
                capability_id="browser_navigate",
                name="Navigate Browser Tab",
                description="Navigate the active browser tab to a specified URL.",
                example_requests=["Go to amazon.com", "Navigate to YouTube", "Open https://google.com"],
                supported_surfaces=["browser_tab"],
                adapter="browser_extension_bridge",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}, "title": {"type": "string"}},
                },
                preconditions=["Browser extension connected", "Active browser tab exists"],
                required_permission_scopes=["action:browser_tab"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=8.0,
                is_idempotent=True,
                verification_method="Post-navigation URL and title returned from extension.",
                required_postconditions=["Tab URL matches requested destination"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 21. Browser Search In Tab
        self.register(
            CapabilityDescriptor(
                capability_id="browser_search_in_tab",
                name="Search In Browser Tab",
                description="Type a search query into the active browser tab search input and submit.",
                example_requests=["Search YouTube for AI agent tutorials", "Search Amazon for headphones"],
                supported_surfaces=["browser_tab"],
                adapter="browser_extension_bridge",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "success": {"type": "boolean"}},
                },
                preconditions=["Browser extension connected", "Active browser tab with search input"],
                required_permission_scopes=["action:browser_tab"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=8.0,
                is_idempotent=False,
                verification_method="Search input populated and form submitted via content script.",
                required_postconditions=["Search submitted to active tab"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 22. File Create and Write
        self.register(
            CapabilityDescriptor(
                capability_id="file_create_write",
                name="Create and Write File",
                description="Create a file at specified path and write text content, verifying written bytes.",
                example_requests=["Create a report on my Desktop", "Save summary to file"],
                supported_surfaces=["local_store"],
                adapter="local_file_adapter",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Target file path"},
                        "content": {"type": "string", "description": "Text content to write"},
                    },
                    "required": ["path", "content"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "bytesWritten": {"type": "integer"},
                        "sha256": {"type": "string"},
                    },
                },
                preconditions=["Target directory is within user profile or workspace"],
                required_permission_scopes=["write:local_file"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Readback verification: read file back, compare content and SHA-256 fingerprint.",
                required_postconditions=["File exists on disk and content matches written text"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 23. File Read
        self.register(
            CapabilityDescriptor(
                capability_id="file_read",
                name="Read File Content",
                description="Read content from a local file safely within permitted workspace/user boundaries.",
                example_requests=["Read config.json", "Inspect main.py", "View report.txt"],
                supported_surfaces=["local_store"],
                adapter="local_file_adapter",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file to read"},
                        "maxLines": {"type": "integer", "description": "Maximum lines to read (default 200)"},
                    },
                    "required": ["path"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "lines": {"type": "integer"},
                        "sha256": {"type": "string"},
                    },
                },
                preconditions=["File exists and is readable"],
                required_permission_scopes=["read:local_file"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Cryptographic SHA-256 fingerprinting of read bytes.",
                required_postconditions=["File content returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 24. File List Directory
        self.register(
            CapabilityDescriptor(
                capability_id="file_list_directory",
                name="List Directory Contents",
                description="List files and subdirectories in an authorized directory with file sizes and modified dates.",
                example_requests=["List files in my project", "Show files in downloads"],
                supported_surfaces=["local_store"],
                adapter="local_file_adapter",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path (defaults to current project)"},
                        "recursive": {"type": "boolean", "description": "Whether to list subdirectories"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {"items": {"type": "array"}},
                },
                preconditions=["Directory exists"],
                required_permission_scopes=["read:local_file"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Directory enumeration via standard filesystem API.",
                required_postconditions=["Directory entries returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 25. Document Ingestion
        self.register(
            CapabilityDescriptor(
                capability_id="document_ingest_file",
                name="Ingest and Parse Document",
                description="Safely extract structured text, metadata, and facts from a user file (.pdf, .docx, .xlsx, .pptx, .csv, .md, .txt, code).",
                example_requests=["Ingest invoice.pdf", "Parse quarterly_report.docx", "Load dataset.xlsx"],
                supported_surfaces=["local_store"],
                adapter="document_ingestion_service",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute or workspace path to document"},
                        "title": {"type": "string", "description": "Optional human-friendly document title"},
                    },
                    "required": ["path"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "sourceId": {"type": "string"},
                        "factsCount": {"type": "integer"},
                        "checksum": {"type": "string"},
                    },
                },
                preconditions=["File exists and is an authorized format"],
                required_permission_scopes=["read:local_document"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=10.0,
                is_idempotent=True,
                verification_method="Facts recorded in context store with SHA-256 provenance.",
                required_postconditions=["Extracted facts available in context store"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 26. Document Search Knowledge
        self.register(
            CapabilityDescriptor(
                capability_id="document_search_knowledge",
                name="Search Ingested Knowledge",
                description="Search structured facts across all ingested project documents by keywords and semantic matching with citations.",
                example_requests=["Find payment terms in contract", "Search for warranty period in manual"],
                supported_surfaces=["local_store"],
                adapter="context_store_adapter",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keyword or question"},
                    },
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"facts": {"type": "array"}},
                },
                preconditions=["Documents ingested into context store"],
                required_permission_scopes=["read:context_facts"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Keyword and provenance matching across ContextFacts.",
                required_postconditions=["Matching facts returned with source IDs"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 27. Document Compare Sources
        self.register(
            CapabilityDescriptor(
                capability_id="document_compare_sources",
                name="Compare Documents and Detect Inconsistencies",
                description="Compare statements across multiple ingested documents, identifying contradictions, price differences, or gaps.",
                example_requests=["Find discrepancies between invoice and purchase order", "Compare specifications"],
                supported_surfaces=["local_store"],
                adapter="document_comparison_service",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Topic or fields to compare"},
                        "sourcePaths": {"type": "array", "description": "List of file paths to compare"},
                    },
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "inconsistencies": {"type": "array"},
                        "alignedFacts": {"type": "array"},
                    },
                },
                preconditions=["At least one source ingested"],
                required_permission_scopes=["read:context_facts"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=10.0,
                is_idempotent=True,
                verification_method="Cross-reference fact matrix comparison with source citations.",
                required_postconditions=["Comparison matrix synthesized"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 28. Tabular Data Analysis
        self.register(
            CapabilityDescriptor(
                capability_id="data_analyze_tabular",
                name="Analyze Tabular Data",
                description="Perform deterministic mathematical, statistical, and SQL analysis on CSV, XLSX, or JSON tables (sums, averages, grouping, filtering).",
                example_requests=["Calculate total revenue and average margin from sales.csv", "Analyze expense spreadsheet"],
                supported_surfaces=["local_store"],
                adapter="data_analysis_runtime",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "File path or CSV data string"},
                        "query": {"type": "string", "description": "Optional SQL query over 'data_table'"},
                    },
                    "required": ["source"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "statistics": {"type": "object"},
                        "markdownPreview": {"type": "string"},
                    },
                },
                preconditions=["Source tabular data exists"],
                required_permission_scopes=["read:local_file"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=10.0,
                is_idempotent=True,
                verification_method="In-memory SQLite schema validation and deterministic computation.",
                required_postconditions=["Computed numerical stats and table returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 29. Artifact Generate Document
        self.register(
            CapabilityDescriptor(
                capability_id="artifact_generate_document",
                name="Generate Word or Markdown Document",
                description="Create a real editable Word (.docx) or Markdown (.md) document with title, executive summary, sections, and citations.",
                example_requests=["Create a complete research report on my Desktop", "Prepare project audit document"],
                supported_surfaces=["local_store"],
                adapter="artifact_generator_service",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Document title"},
                        "sections": {
                            "type": "array",
                            "description": "List of sections with 'heading' and 'content'",
                        },
                        "outputPath": {"type": "string", "description": "Target file path (e.g. '~/Desktop/report.docx')"},
                        "format": {"type": "string", "description": "'docx' or 'md' (default 'docx')"},
                        "sources": {"type": "array", "description": "Optional list of citation strings"},
                    },
                    "required": ["title", "sections", "outputPath"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "filePath": {"type": "string"},
                        "fileSize": {"type": "integer"},
                        "sha256": {"type": "string"},
                    },
                },
                preconditions=["Destination directory is writable"],
                required_permission_scopes=["write:local_file"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=8.0,
                is_idempotent=True,
                verification_method="File write and readback verification with SHA-256 fingerprinting.",
                required_postconditions=["Document exists on disk with verified content"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 30. Artifact Generate Spreadsheet
        self.register(
            CapabilityDescriptor(
                capability_id="artifact_generate_spreadsheet",
                name="Generate Excel Workbook",
                description="Create a real editable Excel (.xlsx) or CSV workbook with headers, rows, and mathematical formulas (e.g. SUM, AVERAGE).",
                example_requests=["Create a product comparison sheet on Desktop", "Export financial budget.xlsx"],
                supported_surfaces=["local_store"],
                adapter="artifact_generator_service",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Workbook title"},
                        "headers": {"type": "array", "description": "Column header names"},
                        "rows": {"type": "array", "description": "2D list of row values"},
                        "outputPath": {"type": "string", "description": "Target file path (e.g. '~/Desktop/budget.xlsx')"},
                        "format": {"type": "string", "description": "'xlsx' or 'csv' (default 'xlsx')"},
                    },
                    "required": ["title", "headers", "rows", "outputPath"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "filePath": {"type": "string"},
                        "fileSize": {"type": "integer"},
                        "sha256": {"type": "string"},
                    },
                },
                preconditions=["Destination directory is writable"],
                required_permission_scopes=["write:local_file"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=8.0,
                is_idempotent=True,
                verification_method="File write and readback verification with SHA-256 fingerprinting.",
                required_postconditions=["Spreadsheet exists on disk with verified rows"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 31. Multi-Hop Web Research
        self.register(
            CapabilityDescriptor(
                capability_id="research_web_multihop",
                name="Conduct Multi-Hop Web Research",
                description="Search the web, fetch top primary sources with SSRF defense, extract factual statements, and return cited evidence.",
                example_requests=["Research market trends in EV batteries", "Find official documentation for React 19"],
                supported_surfaces=["internet"],
                adapter="internet_research_manager",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query or research question"},
                        "maxResults": {"type": "integer", "description": "Number of sources to retrieve (default 4)"},
                    },
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "results": {"type": "array"},
                        "citations": {"type": "array"},
                    },
                },
                preconditions=["Internet connectivity available"],
                required_permission_scopes=["access:public_web"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=15.0,
                is_idempotent=True,
                verification_method="Validation of retrieved page URLs and cryptographic fingerprinting of results.",
                required_postconditions=["Cited web research results returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 32. Windows Enumerate Controls
        self.register(
            CapabilityDescriptor(
                capability_id="windows_enumerate_controls",
                name="Enumerate Windows UI Controls",
                description="Inspect the accessible UI Automation element tree of the active or target window, returning control roles, names, and IDs.",
                example_requests=["Inspect controls in active window", "Find button in Calculator"],
                supported_surfaces=["desktop_window"],
                adapter="windows_native_companion",
                input_schema={
                    "type": "object",
                    "properties": {
                        "hwnd": {"type": "integer", "description": "Optional window handle (defaults to foreground window)"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {"controls": {"type": "array"}},
                },
                preconditions=["Windows Controller running"],
                required_permission_scopes=["read:desktop_window"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="UI Automation tree enumeration.",
                required_postconditions=["Control descriptors returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 33. Windows Invoke Control
        self.register(
            CapabilityDescriptor(
                capability_id="windows_invoke_control",
                name="Invoke Windows Control",
                description="Click, toggle, or invoke an accessible UI Automation control by its AutomationId or Name.",
                example_requests=["Click Equals button in Calculator", "Click Save in Notepad"],
                supported_surfaces=["desktop_window"],
                adapter="windows_native_companion",
                input_schema={
                    "type": "object",
                    "properties": {
                        "controlName": {"type": "string", "description": "Accessible name of the control"},
                        "automationId": {"type": "string", "description": "Optional AutomationId of the control"},
                        "hwnd": {"type": "integer", "description": "Optional target window handle"},
                    },
                    "required": ["controlName"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"success": {"type": "boolean"}},
                },
                preconditions=["Target control exists in active window"],
                required_permission_scopes=["action:desktop_window"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=False,
                is_reversible=False,
                timeout_seconds=5.0,
                is_idempotent=False,
                verification_method="Post-invocation observation of control state change.",
                required_postconditions=["Control invoked"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 34. Browser Get Active Tab
        self.register(
            CapabilityDescriptor(
                capability_id="browser_get_active_tab",
                name="Get Active Browser Tab",
                description="Inspect the active browser tab's URL, page title, and visible text content.",
                example_requests=["Read current page", "What tab is open?"],
                supported_surfaces=["browser_tab"],
                adapter="browser_extension_bridge",
                input_schema={"type": "object", "properties": {}},
                output_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "title": {"type": "string"},
                        "textExcerpt": {"type": "string"},
                    },
                },
                preconditions=["Browser extension connected"],
                required_permission_scopes=["read:browser_tab"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="Active tab query from browser extension bridge.",
                required_postconditions=["Tab observation returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 35. Browser Get Page Content Chunked
        self.register(
            CapabilityDescriptor(
                capability_id="browser_get_page_content",
                name="Get Browser Page Content",
                description="Read full or chunked visible text and accessible interactive controls from the active browser tab.",
                example_requests=["Read full article from webpage", "Inspect page controls and sections", "Search webpage for terms"],
                supported_surfaces=["browser_tab"],
                adapter="browser_extension_bridge",
                input_schema={
                    "type": "object",
                    "properties": {
                        "chunkIndex": {"type": "integer", "description": "0-based chunk index to read"},
                        "chunkSize": {"type": "integer", "description": "Characters per chunk (default 4000)"},
                        "query": {"type": "string", "description": "Optional keyword filter to match relevant page text"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "title": {"type": "string"},
                        "contentChunk": {"type": "string"},
                        "totalTextLength": {"type": "integer"},
                        "chunkIndex": {"type": "integer"},
                        "hasMoreChunks": {"type": "boolean"},
                        "interactiveControls": {"type": "array"},
                    },
                },
                preconditions=["Browser extension connected", "Tab is loaded"],
                required_permission_scopes=["read:browser_tab"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=5.0,
                is_idempotent=True,
                verification_method="DOM observation extraction with SHA-256 fingerprinting.",
                required_postconditions=["Page content chunk returned"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 36. Controlled Workspace Code Execution
        self.register(
            CapabilityDescriptor(
                capability_id="workspace_run_code",
                name="Run Controlled Project Code",
                description="Execute a Python script or code snippet in an authorized workspace without arbitrary shell injection.",
                example_requests=["Run Python script in workspace", "Execute test script and verify stdout", "Write and run hello world"],
                supported_surfaces=["local_store"],
                adapter="workspace_code_runner",
                input_schema={
                    "type": "object",
                    "properties": {
                        "scriptPath": {"type": "string", "description": "Relative or absolute path to .py script in workspace"},
                        "code": {"type": "string", "description": "Optional inline Python code to write and execute"},
                        "workspacePath": {"type": "string", "description": "Optional workspace root directory"},
                        "args": {"type": "array", "items": {"type": "string"}, "description": "Command line arguments for script"},
                        "timeoutSeconds": {"type": "number", "description": "Timeout in seconds (default 30)"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "exitCode": {"type": "integer"},
                        "stdout": {"type": "string"},
                        "stderr": {"type": "string"},
                        "filePath": {"type": "string"},
                        "scriptSha256": {"type": "string"},
                        "durationMs": {"type": "number"},
                    },
                },
                preconditions=["Script exists or code is provided", "Path is inside authorized workspace"],
                required_permission_scopes=["execute:code"],
                risk_category=RiskCategory.MEDIUM,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=30.0,
                is_idempotent=False,
                verification_method="Subprocess execution exit code and stdout observation.",
                required_postconditions=["Process exited and output captured"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 37. Project Workspace & Folder Indexing
        self.register(
            CapabilityDescriptor(
                capability_id="workspace_index_directory",
                name="Index Project Folder",
                description="Scan and index files in an authorized project folder, computing SHA-256 hashes and directory tree.",
                example_requests=["Index project directory", "Scan workspace folder and summarize files", "Analyze code repository"],
                supported_surfaces=["local_store"],
                adapter="workspace_indexer",
                input_schema={
                    "type": "object",
                    "properties": {
                        "directoryPath": {"type": "string", "description": "Path to local folder to index"},
                        "maxDepth": {"type": "integer", "description": "Maximum directory depth (default 4)"},
                        "maxFiles": {"type": "integer", "description": "Maximum files to index (default 150)"},
                    },
                    "required": ["directoryPath"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "workspacePath": {"type": "string"},
                        "totalFilesDiscovered": {"type": "integer"},
                        "files": {"type": "array"},
                        "summary": {"type": "string"},
                    },
                },
                preconditions=["Directory exists"],
                required_permission_scopes=["read:local_file"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=15.0,
                is_idempotent=True,
                verification_method="Filesystem tree enumeration and SHA-256 fingerprinting.",
                required_postconditions=["Files indexed and stored in ledger"],
                readiness_state=CapabilityReadiness.READY,
            )
        )

        # 38. Creative Image Editing & Stylization
        self.register(
            CapabilityDescriptor(
                capability_id="image_edit_style",
                name="Edit and Style Image",
                description="Apply artistic styles (retro, vintage, synthwave, neon) to user or workspace images using Meta muse-image-1.0 and vector stylizers.",
                example_requests=["Edit the image in retro style", "Style this photo in vintage aesthetic", "Apply synthwave styling to image"],
                supported_surfaces=["local_store", "artifact_store"],
                adapter="meta_muse_image",
                input_schema={
                    "type": "object",
                    "properties": {
                        "imagePath": {"type": "string", "description": "Path to local or artifact image to style"},
                        "styleInstruction": {"type": "string", "description": "Artistic style to apply (e.g. retro, synthwave, vintage)"},
                    },
                    "required": ["styleInstruction"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "originalPath": {"type": "string"},
                        "styledPath": {"type": "string"},
                        "styledUrl": {"type": "string"},
                        "artifactId": {"type": "string"},
                        "styleInstruction": {"type": "string"},
                    },
                },
                preconditions=["Source image exists or creative instruction provided"],
                required_permission_scopes=["write:artifact"],
                risk_category=RiskCategory.LOW,
                requires_human_confirmation=False,
                is_reversible=True,
                timeout_seconds=30.0,
                is_idempotent=False,
                verification_method="Generation of styled image artifact file and checksum verification.",
                required_postconditions=["Styled image artifact generated"],
                readiness_state=CapabilityReadiness.READY,
            )
        )


# Global singleton instance
capability_registry = CapabilityRegistry()
