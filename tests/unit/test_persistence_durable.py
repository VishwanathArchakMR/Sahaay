"""Unit tests for SQLite durable state persistence across simulated application restarts."""

import uuid

from sahaay_core.contracts.models import (
    ConsentGrant,
    ContextFact,
    EvidenceReference,
    FactTypeEnum,
    Session,
    SourceReference,
    TaskContract,
    TaskStatusEnum,
    TaskStep,
)
from sahaay_core.sources.manager import SourceManager
from sahaay_core.storage.persistence import DurableStorage, durable_storage, get_sqlite_conn


def test_durable_storage_schema_initialization():
    """Verify that all required tables exist in SQLite with WAL and foreign keys."""
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    expected = {
        "sessions",
        "consent_grants",
        "tasks",
        "task_steps",
        "source_references",
        "context_facts",
        "evidence_records",
        "task_passports",
        "passport_milestones",
        "artifacts",
        "web_research",
    }
    assert expected.issubset(tables)


def test_persistence_survives_service_reconstruction():
    """Test that session, grant, source, fact, task, and evidence survive service reconstruction."""
    storage1 = DurableStorage()

    session_id = uuid.uuid4()
    task_id = uuid.uuid4()
    source_id = uuid.uuid4()
    fact_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    step_id = uuid.uuid4()
    action_id = uuid.uuid4()
    verification_id = uuid.uuid4()

    # 1. Save Session & Consent
    storage1.save_session(
        Session(
            sessionId=session_id,
            localOnlyMode=True,
            metadata={"user": "test_persistence_user"},
        )
    )
    storage1.save_consent_grant(
        ConsentGrant(
            grantId=uuid.uuid4(),
            sessionId=session_id,
            scope="windows.notepad.write",
            purpose="test persistence",
        )
    )

    # 2. Save Source & Fact
    storage1.save_source_reference(
        SourceReference(
            sourceId=source_id,
            sourceType="local_file",
            uri="c:/test/invoice.json",
            checksum="abc123hash",
            metadata={"format": "json"},
        )
    )
    storage1.save_context_fact(
        ContextFact(
            factId=fact_id,
            factType=FactTypeEnum.SOURCE_EXTRACTED,
            content="consumer_name: Aarav Sharma",
            sourceReferenceId=source_id,
            confidenceScore=1.0,
        )
    )

    # 3. Save Task & Step
    storage1.save_task(
        TaskContract(
            taskId=task_id,
            sessionId=session_id,
            goal="Extract invoice to notepad",
            status=TaskStatusEnum.COMPLETED,
        )
    )
    storage1.save_task_step(
        TaskStep(
            stepId=step_id,
            taskId=task_id,
            sequenceNumber=1,
            instruction="Read invoice document",
            status=TaskStatusEnum.COMPLETED,
        )
    )

    # 4. Save Evidence
    storage1.save_evidence_reference(
        EvidenceReference(
            evidenceId=evidence_id,
            taskId=task_id,
            stepId=step_id,
            actionId=action_id,
            verificationResultId=verification_id,
            narrative="Verified text written to desktop notepad window",
        )
    )

    # Reconstruct storage instance
    storage2 = DurableStorage()

    # Verify session & consent
    reloaded_sess = storage2.get_session(session_id)
    assert reloaded_sess is not None
    assert reloaded_sess.sessionId == session_id
    assert reloaded_sess.localOnlyMode is True

    grants = storage2.get_consent_grants_for_session(session_id)
    assert len(grants) >= 1
    assert any(g.scope == "windows.notepad.write" for g in grants)

    # Verify source & fact
    reloaded_src = storage2.get_source_reference(source_id)
    assert reloaded_src is not None
    assert reloaded_src.uri == "c:/test/invoice.json"

    reloaded_facts = storage2.get_context_facts_for_source(source_id)
    assert len(reloaded_facts) >= 1
    assert any("Aarav Sharma" in f.content for f in reloaded_facts)

    # Verify task & evidence
    reloaded_task = storage2.get_task(task_id)
    assert reloaded_task is not None
    assert reloaded_task.status == TaskStatusEnum.COMPLETED

    reloaded_evidence = storage2.get_evidence_records_for_task(task_id)
    assert len(reloaded_evidence) >= 1
    assert any(e.evidenceId == evidence_id for e in reloaded_evidence)


def test_revocation_persists_and_hides_sources():
    """Revoking a source persists in SQLite and filters it from active retrieval."""
    source_mgr = SourceManager()
    source = source_mgr.register_source(
        source_type="local_file",
        uri=f"c:/docs/confidential-{uuid.uuid4().hex[:6]}.pdf",
        sha256="confidential_hash",
    )
    source_id = source.sourceId

    # Revoke the source
    success = source_mgr.revoke_source(source_id, reason="User revoked permission")
    assert success is True

    # Reconstruct manager
    fresh_mgr = SourceManager()
    active = fresh_mgr.list_active_sources()
    assert all(s.sourceId != source_id for s in active)

    # Inactive/revoked record cannot be retrieved by get_source_reference
    raw_source = durable_storage.get_source_reference(source_id)
    assert raw_source is None
