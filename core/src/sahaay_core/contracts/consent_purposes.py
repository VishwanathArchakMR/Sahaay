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

