"""SQLAlchemy Relational Models for Sahaay SQLite Persistence."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SessionRecord(Base):
    __tablename__ = "sessions"

    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    local_only_mode = Column(Boolean, default=True, nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)


class ConsentGrantRecord(Base):
    __tablename__ = "consent_grants"

    grant_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=False)
    scope = Column(String(255), nullable=False)
    purpose = Column(String(255), nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    target_domain_or_path = Column(String(512), nullable=True)


class TaskRecord(Base):
    __tablename__ = "tasks"

    task_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=False)
    goal = Column(Text, nullable=False)
    task_type = Column(String(64), default="combined_retrieval_and_action", nullable=False)
    status = Column(String(64), default="CREATED", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class TaskStepRecord(Base):
    __tablename__ = "task_steps"

    step_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.task_id"), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    instruction = Column(Text, nullable=False)
    status = Column(String(64), default="CREATED", nullable=False)
    action_json = Column(Text, nullable=True)
    policy_decision = Column(String(32), nullable=True)
    verification_status = Column(String(32), nullable=True)


class SourceReferenceRecord(Base):
    __tablename__ = "source_references"

    source_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_type = Column(String(64), nullable=False)
    uri = Column(String(1024), nullable=False)
    observed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    title = Column(String(512), nullable=True)
    checksum = Column(String(128), nullable=True)
    metadata_json = Column(Text, default="{}", nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


class ContextFactRecord(Base):
    __tablename__ = "context_facts"

    fact_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    fact_type = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    source_reference_id = Column(
        String(36), ForeignKey("source_references.source_id"), nullable=False
    )
    derivation_ids_json = Column(Text, default="[]", nullable=False)
    confidence_score = Column(Float, default=1.0, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)


class ObservationRecord(Base):
    __tablename__ = "observations"

    observation_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.task_id"), nullable=True)
    step_id = Column(String(36), nullable=True)
    environment_type = Column(String(64), nullable=False)
    window_title = Column(String(512), nullable=True)
    url = Column(String(1024), nullable=True)
    dom_snapshot_ref = Column(String(1024), nullable=True)
    screenshot_ref = Column(String(1024), nullable=True)
    extracted_text = Column(Text, nullable=True)
    metadata_json = Column(Text, default="{}", nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    evidence_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.task_id"), nullable=False)
    step_id = Column(String(36), nullable=False)
    action_id = Column(String(36), nullable=False)
    observation_id = Column(String(36), nullable=True)
    verification_result_id = Column(String(36), nullable=False)
    verification_status = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    narrative = Column(Text, nullable=False)


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    session_id = Column(String(36), nullable=True)
    task_id = Column(String(36), nullable=True)
    event_type = Column(String(128), nullable=False)
    actor = Column(String(64), nullable=False)
    payload_sanitized_json = Column(Text, default="{}", nullable=False)


class TaskPassportRecord(Base):
    __tablename__ = "task_passports"

    task_id = Column(String(36), primary_key=True)
    goal = Column(Text, nullable=False)
    workflow_mode = Column(String(64), default="combined_retrieval_and_action", nullable=False)
    source_to_target = Column(String(255), nullable=True)
    verification_status = Column(String(32), nullable=False)
    total_milestones = Column(Integer, default=0, nullable=False)
    summary_notice = Column(Text, nullable=True)
    provenance_sha256 = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PassportMilestoneRecord(Base):
    __tablename__ = "passport_milestones"

    milestone_id = Column(String(64), primary_key=True)
    task_id = Column(String(36), ForeignKey("task_passports.task_id"), nullable=False)
    step_index = Column(Integer, default=1, nullable=False)
    milestone_type = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(32), nullable=False)
    direction = Column(String(128), nullable=True)
    source_reference = Column(String(1024), nullable=True)
    evidence_id = Column(String(64), nullable=True)
    illustration_url = Column(String(1024), nullable=True)
    svg_fallback = Column(Text, nullable=False)
    is_ai_generated = Column(Boolean, default=False, nullable=False)
    ai_label = Column(String(64), default="Vector Illustration", nullable=False)
    timestamp = Column(String(64), nullable=False)
    technical_details_json = Column(Text, default="{}", nullable=False)


class ArtifactRecord(Base):
    __tablename__ = "artifacts"

    artifact_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id = Column(String(36), nullable=False)
    artifact_type = Column(String(64), default="image", nullable=False)
    file_path = Column(String(1024), nullable=False)
    prompt_hash = Column(String(128), nullable=True)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)


class WebResearchRecord(Base):
    __tablename__ = "web_research"

    research_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    query = Column(Text, nullable=False)
    provider = Column(String(64), default="keyless_web_search", nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    results_json = Column(Text, default="[]", nullable=False)
    citations_json = Column(Text, default="[]", nullable=False)
    status = Column(String(32), default="COMPLETED", nullable=False)


# Backward-compatible convenience aliases
SourceRecord = SourceReferenceRecord
FactRecord = ContextFactRecord
