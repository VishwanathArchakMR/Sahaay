"""Capability Registry Models for Sahaay.

Defines the schema for authoritative capability descriptors including security,
verification, risk, and runtime properties.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class RiskCategory(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CapabilityReadiness(str, Enum):
    READY = "READY"
    CONFIGURED_UNTESTED = "CONFIGURED_UNTESTED"
    NEEDS_CONSENT = "NEEDS_CONSENT"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"


class CapabilityDescriptor(BaseModel):
    """Authoritative descriptor for an executable capability in Sahaay."""

    capability_id: str = Field(..., description="Stable unique identifier for the capability")
    name: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Clear explanation of the operation")
    example_requests: List[str] = Field(
        default_factory=list, description="Natural language examples"
    )
    supported_surfaces: List[str] = Field(
        ..., description="browser_tab, desktop_window, local_store, internet"
    )
    adapter: str = Field(..., description="Name of the native adapter backing this capability")
    input_schema: Dict[str, Any] = Field(
        default_factory=dict, description="Typed input JSON schema"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict, description="Typed output JSON schema"
    )
    preconditions: List[str] = Field(
        default_factory=list, description="Required state before execution"
    )
    required_permission_scopes: List[str] = Field(
        default_factory=list, description="Scopes needed in ConsentGrant"
    )
    risk_category: RiskCategory = Field(
        default=RiskCategory.MEDIUM, description="Risk classification"
    )
    requires_human_confirmation: bool = Field(
        default=False, description="Whether Action Gate requires user prompt"
    )
    is_reversible: bool = Field(default=False, description="Whether the action can be undone")
    potential_side_effects: List[str] = Field(
        default_factory=list, description="Possible permanent state changes"
    )
    timeout_seconds: float = Field(default=10.0, description="Execution timeout limit")
    supports_cancellation: bool = Field(
        default=True, description="Whether in-flight action can be halted"
    )
    is_idempotent: bool = Field(
        default=False, description="Whether re-execution is safe without side-effects"
    )
    retry_count: int = Field(default=0, description="Safe automatic retry attempts")
    verification_method: str = Field(..., description="Method used by independent verifier")
    required_postconditions: List[str] = Field(
        default_factory=list, description="Expected observable post-conditions"
    )
    readiness_state: CapabilityReadiness = Field(
        default=CapabilityReadiness.READY, description="Runtime readiness"
    )
    known_limitations: List[str] = Field(
        default_factory=list, description="Unsupported conditions or constraints"
    )
