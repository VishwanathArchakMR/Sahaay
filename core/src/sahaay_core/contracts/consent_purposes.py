"""Canonical Consent Purposes for Sahaay and Meta Cloud Inference.

Defines authoritative constants and enumerations for all outbound Meta Cloud
processing purposes and local computer-use capability authorizations.
"""

from enum import Enum


class MetaCloudConsentPurpose(str, Enum):
    """Canonical purpose identifiers for Meta Cloud inference."""

    TASK_PLANNING = "task_planning"
    AUDIO_TRANSCRIPTION = "audio_transcription"
    BROWSER_CONTENT = "browser_content"
    BROWSER_SCREENSHOTS = "browser_screenshots"
    DESKTOP_SCREENSHOTS = "desktop_screenshots"
    DOCUMENT_ANALYSIS = "document_analysis"
    MULTIMODAL_REASONING = "multimodal_reasoning"


ALL_META_CLOUD_PURPOSES = [
    MetaCloudConsentPurpose.TASK_PLANNING.value,
    MetaCloudConsentPurpose.AUDIO_TRANSCRIPTION.value,
    MetaCloudConsentPurpose.BROWSER_CONTENT.value,
    MetaCloudConsentPurpose.BROWSER_SCREENSHOTS.value,
    MetaCloudConsentPurpose.DESKTOP_SCREENSHOTS.value,
    MetaCloudConsentPurpose.DOCUMENT_ANALYSIS.value,
    MetaCloudConsentPurpose.MULTIMODAL_REASONING.value,
]

# Canonical Meta provider destination endpoint
META_API_DESTINATION = "https://api.meta.ai/v1"

# Canonical Local Computer-Use and Automation Scopes
LOCAL_AUTOMATION_SCOPES = [
    "computer_use",
    "desktop_automation",
    "browser_automation",
    "launch_application",
    "focus_window",
    "click_desktop_control",
    "type_desktop_text",
    "set_control_text",
    "get_control_text",
    "navigate_browser_tab",
    "click_browser_element",
    "input_browser_text",
    "fill_form_fields",
    "get_field_values",
    "set_system_volume",
    "get_system_volume",
    "windows_launch_app",
    "windows_set_control_text",
    "windows_click_control",
    "windows_invoke_control",
    "windows_set_volume",
    "windows_get_volume",
    "windows_enumerate_controls",
    "windows_inspect_window",
    "windows_get_control_text",
    "browser_open_tab",
    "browser_navigate",
    "browser_click_element",
    "browser_fill_form",
    "browser_scroll_tab",
    "browser_search_in_tab",
    "browser_get_active_tab",
    "browser_get_page_content",
    "browser_tab_observe",
    "browser_get_values",
    "file_create_write",
    "file_read",
    "file_list_directory",
    "workspace_run_code",
    "workspace_index_directory",
    "artifact_generate",
    "artifact_generate_document",
    "artifact_generate_spreadsheet",
    "data_analyze_tabular",
    "document_ingest_file",
    "document_search_knowledge",
    "document_compare_sources",
    "research_web_search",
    "research_web_multihop",
]

