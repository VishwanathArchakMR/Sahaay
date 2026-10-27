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


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    evidence_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.task_id"), nullable=False)
    step_id = Column(String(36), ForeignKey("task_steps.step_id"), nullable=False)
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
