"""Authoritative Python Pydantic Models for Sahaay Contracts v1.

Matches shared/schemas/contracts.v1.json.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyDecisionEnum(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    CLARIFY = "CLARIFY"
    HANDOFF = "HANDOFF"
    REOBSERVE = "REOBSERVE"


class VerificationStatusEnum(str, Enum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICT = "CONFLICT"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


class FactTypeEnum(str, Enum):
    USER_PROVIDED = "user-provided"
    SOURCE_EXTRACTED = "source-extracted"
    OBSERVED = "observed"
    NORMALIZED = "normalized"
    INFERRED = "inferred"
    UNCERTAIN = "uncertain"
    CONFLICTING = "conflicting"


class TaskStatusEnum(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    OBSERVING = "OBSERVING"
    PROPOSING = "PROPOSING"
    AUTHORIZING = "AUTHORIZING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    HANDOFF_REQUESTED = "HANDOFF_REQUESTED"


class DataClassificationEnum(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SENSITIVE_PII = "SENSITIVE_PII"
    CREDENTIAL = "CREDENTIAL"
    HIGHLY_RESTRICTED = "HIGHLY_RESTRICTED"


class ActionTypeEnum(str, Enum):
    READ_FILE = "read_file"
    SEARCH_FILES = "search_files"
    GET_ACTIVE_TAB_INFO = "get_active_tab_info"
    GET_TAB_CONTENT = "get_tab_content"
    NAVIGATE_BROWSER_TAB = "navigate_browser_tab"
    CLICK_BROWSER_ELEMENT = "click_browser_element"
    INPUT_BROWSER_TEXT = "input_browser_text"
    FOCUS_WINDOW = "focus_window"
    GET_ACTIVE_WINDOW = "get_active_window"
    LIST_OPEN_WINDOWS = "list_open_windows"
    CLICK_DESKTOP_CONTROL = "click_desktop_control"
    TYPE_DESKTOP_TEXT = "type_desktop_text"
    SET_CONTROL_TEXT = "set_control_text"
    GET_CONTROL_TEXT = "get_control_text"
    SCROLL_BROWSER_TAB = "scroll_browser_tab"
    FILL_FORM_FIELDS = "fill_form_fields"
    GET_FIELD_VALUES = "get_field_values"
    LAUNCH_APPLICATION = "launch_application"
    SET_SYSTEM_VOLUME = "set_system_volume"
    GET_SYSTEM_VOLUME = "get_system_volume"
    RESEARCH_WEB_SEARCH = "research_web_search"
    RESEARCH_FETCH_PAGE = "research_fetch_page"
    DOCUMENT_INGEST_CHUNK = "document_ingest_chunk"
    DETERMINISTIC_RETRIEVAL = "deterministic_retrieval"
    VERIFY_READBACK = "verify_readback"
    USER_AUTHORIZATION = "user_authorization"


class Session(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sessionId: UUID = Field(default_factory=uuid4)
    createdAt: datetime = Field(default_factory=utc_now)
    expiresAt: Optional[datetime] = None
    isActive: bool = True
    localOnlyMode: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConsentGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grantId: UUID = Field(default_factory=uuid4)
    sessionId: UUID
    scope: str
    purpose: str
    grantedAt: datetime = Field(default_factory=utc_now)
    expiresAt: Optional[datetime] = None
    isRevoked: bool = False
    revokedAt: Optional[datetime] = None
    targetDomainOrPath: Optional[str] = None


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceId: UUID = Field(default_factory=uuid4)
    sourceType: str  # local_file, browser_tab, desktop_window, user_input, system_state
    uri: str
    observedAt: datetime = Field(default_factory=utc_now)
    title: Optional[str] = None
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    factId: UUID = Field(default_factory=uuid4)
    factType: FactTypeEnum
    content: str
    sourceReferenceId: UUID
    derivationIds: List[UUID] = Field(default_factory=list)
    confidenceScore: float = Field(default=1.0, ge=0.0, le=1.0)
    recordedAt: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observationId: UUID = Field(default_factory=uuid4)
    taskId: UUID
    stepId: UUID
    capturedAt: datetime = Field(default_factory=utc_now)
    environmentType: str  # windows_desktop, browser_active_tab, file_system
    windowTitle: Optional[str] = None
    url: Optional[str] = None
    domSnapshotRef: Optional[str] = None
    screenshotRef: Optional[str] = None
    extractedText: Optional[str] = None
    elementTree: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actionId: UUID = Field(default_factory=uuid4)
    actionType: ActionTypeEnum
    target: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    expectedPostcondition: str
    estimatedRisk: str = Field(default="LOW")  # READ_ONLY, LOW, MEDIUM, HIGH


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decisionId: UUID = Field(default_factory=uuid4)
    actionId: UUID
    decision: PolicyDecisionEnum
    reason: str
    requiredGrantScope: Optional[str] = None
    clarificationPrompt: Optional[str] = None
    evaluatedAt: datetime = Field(default_factory=utc_now)


class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    executionId: UUID = Field(default_factory=uuid4)
    actionId: UUID
    isSuccess: bool
    executedAt: datetime = Field(default_factory=utc_now)
    durationMs: float = Field(ge=0.0)
    outputData: Optional[Dict[str, Any]] = None
    errorMessage: Optional[str] = None


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verificationId: UUID = Field(default_factory=uuid4)
    actionId: UUID
    status: VerificationStatusEnum
    verifierType: str  # deterministic_state_check, dom_property_check, file_checksum_check, human_confirmation
    details: str
    observedPostcondition: Optional[str] = None
    verifiedAt: datetime = Field(default_factory=utc_now)


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidenceId: UUID = Field(default_factory=uuid4)
    taskId: UUID
    stepId: UUID
    actionId: UUID
    observationId: Optional[UUID] = None
    verificationResultId: UUID
    createdAt: datetime = Field(default_factory=utc_now)
    narrative: str


class TaskStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stepId: UUID = Field(default_factory=uuid4)
    taskId: UUID
    sequenceNumber: int = Field(ge=1)
    instruction: str
    status: TaskStatusEnum = TaskStatusEnum.CREATED
    action: Optional[ActionContract] = None
    policyDecision: Optional[PolicyDecisionEnum] = None
    verificationStatus: Optional[VerificationStatusEnum] = None
    capabilityId: Optional[str] = None
    intendedOutcome: Optional[str] = None
    dependencies: List[UUID] = Field(default_factory=list)
    inputFacts: Dict[str, Any] = Field(default_factory=dict)
    requiredPermissionScopes: List[str] = Field(default_factory=list)
    riskCategory: str = "LOW"
    requiresHumanConfirmation: bool = False
    timeoutSeconds: float = 10.0
    isIdempotent: bool = False
    maxRetries: int = 0
    retryCount: int = 0
    evidenceRequired: Optional[str] = None
    failureHandoff: bool = False
    outputData: Optional[Dict[str, Any]] = None
    errorMessage: Optional[str] = None


class TaskContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    taskId: UUID = Field(default_factory=uuid4)
    sessionId: UUID
    goal: str
    taskType: str = "combined_retrieval_and_action"  # retrieval_only, action_only, combined_retrieval_and_action
    status: TaskStatusEnum = TaskStatusEnum.CREATED
    createdAt: datetime = Field(default_factory=utc_now)
    completedAt: Optional[datetime] = None
    steps: List[TaskStep] = Field(default_factory=list)


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eventId: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=utc_now)
    sessionId: Optional[UUID] = None
    taskId: Optional[UUID] = None
    eventType: str
    actor: str  # user, policy_engine, action_gate, orchestrator, verifier
    payloadSanitized: Dict[str, Any] = Field(default_factory=dict)


class ModelCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    provider: str
    isAvailable: bool
    isLocal: bool
    purpose: str
    contextWindowTokens: Optional[int] = None


class CapabilityDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    systemVersion: str
    desktopAutomationAvailable: bool = False
    browserAutomationAvailable: bool = False
    modelsAvailable: List[ModelCapability] = Field(default_factory=list)
    activeCapabilities: List[str] = Field(default_factory=list)


class PrivacyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decisionId: UUID = Field(default_factory=uuid4)
    allowTransmission: bool
    destination: str
    dataClassification: DataClassificationEnum
    reason: str
    evaluatedAt: datetime = Field(default_factory=utc_now)
