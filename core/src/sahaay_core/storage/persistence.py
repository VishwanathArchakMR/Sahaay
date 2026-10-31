"""Durable SQLite Persistence Layer for Sahaay.

Provides reliable, synchronous and asynchronous state persistence to ensure
sessions, consent grants, sources, facts, evidence, tasks, and task passports
survive process restarts and can be audited deterministically.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sahaay_core.config.settings import settings
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
    VerificationStatusEnum,
)


def get_sqlite_conn() -> sqlite3.Connection:
    """Returns a thread-safe connection to the configured SQLite database file."""
    db_path = settings.sync_database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_persistence_schema() -> None:
    """Idempotently initializes all relational tables in SQLite."""
    conn = get_sqlite_conn()
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                local_only_mode INTEGER NOT NULL DEFAULT 1,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS consent_grants (
                grant_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                purpose TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                expires_at TEXT,
                is_revoked INTEGER NOT NULL DEFAULT 0,
                revoked_at TEXT,
                target_domain_or_path TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS source_references (
                source_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                uri TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                title TEXT,
                checksum TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                is_revoked INTEGER NOT NULL DEFAULT 0,
                revoked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS context_facts (
                fact_id TEXT PRIMARY KEY,
                fact_type TEXT NOT NULL,
                content TEXT NOT NULL,
                source_reference_id TEXT NOT NULL,
                derivation_ids_json TEXT NOT NULL DEFAULT '[]',
                confidence_score REAL NOT NULL DEFAULT 1.0,
                recorded_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (source_reference_id) REFERENCES source_references(source_id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                goal TEXT NOT NULL,
                task_type TEXT NOT NULL DEFAULT 'combined_retrieval_and_action',
                status TEXT NOT NULL DEFAULT 'CREATED',
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS task_steps (
                step_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                sequence_number INTEGER NOT NULL,
                instruction TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'CREATED',
                action_json TEXT,
                policy_decision TEXT,
                verification_status TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            );

            CREATE TABLE IF NOT EXISTS evidence_records (
                evidence_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                action_id TEXT NOT NULL,
                observation_id TEXT,
                verification_result_id TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                narrative TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS task_passports (
                task_id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                workflow_mode TEXT NOT NULL,
                source_to_target TEXT,
                verification_status TEXT NOT NULL,
                total_milestones INTEGER NOT NULL DEFAULT 0,
                summary_notice TEXT,
                provenance_sha256 TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS passport_milestones (
                milestone_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_index INTEGER NOT NULL DEFAULT 1,
                milestone_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                direction TEXT,
                source_reference TEXT,
                evidence_id TEXT,
                illustration_url TEXT,
                svg_fallback TEXT NOT NULL,
                is_ai_generated INTEGER NOT NULL DEFAULT 0,
                ai_label TEXT NOT NULL DEFAULT 'Vector Illustration',
                timestamp TEXT NOT NULL,
                technical_details_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (task_id) REFERENCES task_passports(task_id)
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL DEFAULT 'image',
                file_path TEXT NOT NULL,
                prompt_hash TEXT,
                file_size_bytes INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                deleted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS web_research (
                research_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'keyless_web_search',
                timestamp TEXT NOT NULL,
                results_json TEXT NOT NULL DEFAULT '[]',
                citations_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'COMPLETED'
            );
            """
        )
    conn.close()


class DurableStorage:
    """Authoritative SQLite database manager for state persistence."""

    def __init__(self) -> None:
        init_persistence_schema()

    # --- Sessions & Grants ---
    def save_session(self, session: Session) -> None:
        conn = get_sqlite_conn()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (session_id, created_at, expires_at, is_active, local_only_mode, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(session.sessionId),
                    session.createdAt.isoformat(),
                    session.expiresAt.isoformat() if session.expiresAt else None,
                    1 if session.isActive else 0,
                    1 if session.localOnlyMode else 0,
                    json.dumps(session.metadata),
                ),
            )
        conn.close()

    def get_session(self, session_id: UUID) -> Optional[Session]:
        conn = get_sqlite_conn()
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (str(session_id),)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return Session(
            sessionId=UUID(row["session_id"]),
            createdAt=datetime.fromisoformat(row["created_at"]),
            expiresAt=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            isActive=bool(row["is_active"]),
            localOnlyMode=bool(row["local_only_mode"]),
            metadata=json.loads(row["metadata_json"]),
        )

    def save_consent_grant(self, grant: ConsentGrant) -> None:
        conn = get_sqlite_conn()
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions (session_id, created_at, is_active, local_only_mode, metadata_json)
                VALUES (?, ?, 1, 1, '{}')
                """,
                (str(grant.sessionId), grant.grantedAt.isoformat()),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO consent_grants (grant_id, session_id, scope, purpose, granted_at, expires_at, is_revoked, revoked_at, target_domain_or_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(grant.grantId),
                    str(grant.sessionId),
                    grant.scope,
                    grant.purpose,
                    grant.grantedAt.isoformat(),
                    grant.expiresAt.isoformat() if grant.expiresAt else None,
                    1 if grant.isRevoked else 0,
                    grant.revokedAt.isoformat() if grant.revokedAt else None,
                    grant.targetDomainOrPath,
                ),
            )
        conn.close()

    def get_consent_grants_for_session(self, session_id: UUID) -> List[ConsentGrant]:
        conn = get_sqlite_conn()
        rows = conn.execute(
            "SELECT * FROM consent_grants WHERE session_id = ? AND is_revoked = 0",
            (str(session_id),),
        ).fetchall()
        conn.close()
        grants = []
        for r in rows:
            grants.append(
                ConsentGrant(
                    grantId=UUID(r["grant_id"]),
                    sessionId=UUID(r["session_id"]),
                    scope=r["scope"],
                    purpose=r["purpose"],
                    grantedAt=datetime.fromisoformat(r["granted_at"]),
                    expiresAt=datetime.fromisoformat(r["expires_at"]) if r["expires_at"] else None,
                    isRevoked=bool(r["is_revoked"]),
                    revokedAt=datetime.fromisoformat(r["revoked_at"]) if r["revoked_at"] else None,
                    targetDomainOrPath=r["target_domain_or_path"],
                )
            )
        return grants

    # --- Sources ---
    def save_source(self, source: SourceReference) -> None:
        conn = get_sqlite_conn()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO source_references (source_id, source_type, uri, observed_at, title, checksum, metadata_json, is_revoked)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    str(source.sourceId),
                    source.sourceType,
                    source.uri,
                    source.observedAt.isoformat(),
                    source.title,
                    source.checksum,
                    json.dumps(source.metadata),
                ),
            )
        conn.close()

    def get_source(self, source_id: UUID) -> Optional[SourceReference]:
        conn = get_sqlite_conn()
        row = conn.execute(
            "SELECT * FROM source_references WHERE source_id = ? AND is_revoked = 0",
            (str(source_id),),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return SourceReference(
            sourceId=UUID(row["source_id"]),
            sourceType=row["source_type"],
            uri=row["uri"],
            observedAt=datetime.fromisoformat(row["observed_at"]),
            title=row["title"],
            checksum=row["checksum"],
            metadata=json.loads(row["metadata_json"]),
        )

    def revoke_source(self, source_id: UUID) -> bool:
        conn = get_sqlite_conn()
        with conn:
            cur = conn.execute(
                """
                UPDATE source_references
                SET is_revoked = 1, revoked_at = ?
                WHERE source_id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), str(source_id)),
            )
            count = cur.rowcount
        conn.close()
        return count > 0

    def list_active_sources(self) -> List[SourceReference]:
        conn = get_sqlite_conn()
        rows = conn.execute(
            "SELECT * FROM source_references WHERE is_revoked = 0 ORDER BY observed_at DESC"
        ).fetchall()
        conn.close()
        return [
            SourceReference(
                sourceId=UUID(r["source_id"]),
                sourceType=r["source_type"],
                uri=r["uri"],
                observedAt=datetime.fromisoformat(r["observed_at"]),
                title=r["title"],
                checksum=r["checksum"],
                metadata=json.loads(r["metadata_json"]),
            )
            for r in rows
        ]

    # --- Facts ---
    def save_fact(self, fact: ContextFact) -> None:
        conn = get_sqlite_conn()
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO source_references (source_id, source_type, uri, observed_at, title, is_revoked)
                VALUES (?, 'unregistered', 'urn:source:' || ?, ?, 'Referenced Source', 0)
                """,
                (
                    str(fact.sourceReferenceId),
                    str(fact.sourceReferenceId),
                    fact.recordedAt.isoformat(),
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO context_facts (fact_id, fact_type, content, source_reference_id, derivation_ids_json, confidence_score, recorded_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(fact.factId),
                    fact.factType.value if hasattr(fact.factType, "value") else str(fact.factType),
                    fact.content,
                    str(fact.sourceReferenceId),
                    json.dumps([str(d) for d in fact.derivationIds]),
                    fact.confidenceScore,
                    fact.recordedAt.isoformat(),
                    json.dumps(fact.metadata),
                ),
            )
        conn.close()

    def get_fact(self, fact_id: UUID) -> Optional[ContextFact]:
        conn = get_sqlite_conn()
        row = conn.execute(
            "SELECT * FROM context_facts WHERE fact_id = ?", (str(fact_id),)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return ContextFact(
            factId=UUID(row["fact_id"]),
            factType=FactTypeEnum(row["fact_type"]),
            content=row["content"],
            sourceReferenceId=UUID(row["source_reference_id"]),
            derivationIds=[UUID(d) for d in json.loads(row["derivation_ids_json"])],
            confidenceScore=row["confidence_score"],
            recordedAt=datetime.fromisoformat(row["recorded_at"]),
            metadata=json.loads(row["metadata_json"]),
        )

    def get_facts_for_source(self, source_id: UUID) -> List[ContextFact]:
        conn = get_sqlite_conn()
        rows = conn.execute(
            "SELECT * FROM context_facts WHERE source_reference_id = ? ORDER BY recorded_at ASC",
            (str(source_id),),
        ).fetchall()
        conn.close()
        return [
            ContextFact(
                factId=UUID(r["fact_id"]),
                factType=FactTypeEnum(r["fact_type"]),
                content=r["content"],
                sourceReferenceId=UUID(r["source_reference_id"]),
                derivationIds=[UUID(d) for d in json.loads(r["derivation_ids_json"])],
                confidenceScore=r["confidence_score"],
                recordedAt=datetime.fromisoformat(r["recorded_at"]),
                metadata=json.loads(r["metadata_json"]),
            )
            for r in rows
        ]

    # --- Evidence ---
    def save_evidence(self, evidence: EvidenceReference) -> None:
        conn = get_sqlite_conn()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evidence_records (evidence_id, task_id, step_id, action_id, observation_id, verification_result_id, verification_status, created_at, narrative)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(evidence.evidenceId),
                    str(evidence.taskId),
                    str(evidence.stepId),
                    str(evidence.actionId),
                    str(evidence.observationId) if evidence.observationId else None,
                    str(evidence.verificationResultId),
                    "VERIFIED",
                    evidence.createdAt.isoformat(),
                    evidence.narrative,
                ),
            )
        conn.close()

    def get_evidence_for_task(self, task_id: UUID) -> List[EvidenceReference]:
        conn = get_sqlite_conn()
        rows = conn.execute(
            "SELECT * FROM evidence_records WHERE task_id = ? ORDER BY created_at ASC",
            (str(task_id),),
        ).fetchall()
        conn.close()
        return [
            EvidenceReference(
                evidenceId=UUID(r["evidence_id"]),
                taskId=UUID(r["task_id"]),
                stepId=UUID(r["step_id"]),
                actionId=UUID(r["action_id"]),
                observationId=UUID(r["observation_id"]) if r["observation_id"] else None,
                verificationResultId=UUID(r["verification_result_id"]),
                createdAt=datetime.fromisoformat(r["created_at"]),
                narrative=r["narrative"],
            )
            for r in rows
        ]

    # --- Tasks & Steps ---
    def save_task(self, task: TaskContract) -> None:
        conn = get_sqlite_conn()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (task_id, session_id, goal, task_type, status, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(task.taskId),
                    str(task.sessionId),
                    task.goal,
                    task.taskType,
                    task.status.value if hasattr(task.status, "value") else str(task.status),
                    task.createdAt.isoformat(),
                    task.completedAt.isoformat() if task.completedAt else None,
                ),
            )
        conn.close()

    def get_task(self, task_id: UUID) -> Optional[TaskContract]:
        conn = get_sqlite_conn()
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (str(task_id),)).fetchone()
        conn.close()
        if not row:
            return None
        steps = self.get_task_steps(task_id)
        return TaskContract(
            taskId=UUID(row["task_id"]),
            sessionId=UUID(row["session_id"]),
            goal=row["goal"],
            taskType=row["task_type"],
            status=TaskStatusEnum(row["status"]),
            createdAt=datetime.fromisoformat(row["created_at"]),
            completedAt=datetime.fromisoformat(row["completed_at"])
            if row["completed_at"]
            else None,
            steps=steps,
        )

    def save_task_step(self, step: TaskStep) -> None:
        conn = get_sqlite_conn()
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO tasks (task_id, session_id, goal, task_type, status, created_at)
                VALUES (?, '00000000-0000-0000-0000-000000000000', 'Task', 'combined_retrieval_and_action', 'CREATED', ?)
                """,
                (str(step.taskId), datetime.now(timezone.utc).isoformat()),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO task_steps (step_id, task_id, sequence_number, instruction, status, action_json, policy_decision, verification_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(step.stepId),
                    str(step.taskId),
                    step.sequenceNumber,
                    step.instruction,
                    step.status.value if hasattr(step.status, "value") else str(step.status),
                    step.action.model_dump_json() if step.action else None,
                    step.policyDecision.value if step.policyDecision else None,
                    step.verificationStatus.value if step.verificationStatus else None,
                ),
            )
        conn.close()

    def get_task_steps(self, task_id: UUID) -> List[TaskStep]:
        conn = get_sqlite_conn()
        rows = conn.execute(
            "SELECT * FROM task_steps WHERE task_id = ? ORDER BY sequence_number ASC",
            (str(task_id),),
        ).fetchall()
        conn.close()
        steps = []
        for r in rows:
            steps.append(
                TaskStep(
                    stepId=UUID(r["step_id"]),
                    taskId=UUID(r["task_id"]),
                    sequenceNumber=r["sequence_number"],
                    instruction=r["instruction"],
                    status=TaskStatusEnum(r["status"]),
                    policyDecision=r["policy_decision"],
                    verificationStatus=VerificationStatusEnum(r["verification_status"])
                    if r["verification_status"]
                    else None,
                )
            )
        return steps

    def list_tasks(self, limit: int = 50) -> List[TaskContract]:
        conn = get_sqlite_conn()
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        tasks = []
        for row in rows:
            steps = self.get_task_steps(UUID(row["task_id"]))
            tasks.append(
                TaskContract(
                    taskId=UUID(row["task_id"]),
                    sessionId=UUID(row["session_id"]),
                    goal=row["goal"],
                    taskType=row["task_type"],
                    status=TaskStatusEnum(row["status"]),
                    createdAt=datetime.fromisoformat(row["created_at"]),
                    completedAt=datetime.fromisoformat(row["completed_at"])
                    if row["completed_at"]
                    else None,
                    steps=steps,
                )
            )
        return tasks

    # --- Task Passports & Milestones ---
    def save_task_passport(self, passport_data: Dict[str, Any]) -> None:
        conn = get_sqlite_conn()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO task_passports (task_id, goal, workflow_mode, source_to_target, verification_status, total_milestones, summary_notice, provenance_sha256, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    passport_data["taskId"],
                    passport_data.get("goal", ""),
                    passport_data.get("workflowMode", "combined_retrieval_and_action"),
                    passport_data.get("sourceToTarget"),
                    passport_data.get("verificationStatus", "UNVERIFIED"),
                    passport_data.get("totalMilestones", len(passport_data.get("milestones", []))),
                    passport_data.get("summaryNotice"),
                    passport_data.get("provenanceSha256"),
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            # Milestones
            for m in passport_data.get("milestones", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO passport_milestones (
                        milestone_id, task_id, step_index, milestone_type, title, description, status, direction, source_reference, evidence_id, illustration_url, svg_fallback, is_ai_generated, ai_label, timestamp, technical_details_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        m["milestoneId"],
                        passport_data["taskId"],
                        m.get("stepIndex", 1),
                        m.get("milestoneType", "generic"),
                        m.get("title", ""),
                        m.get("description", ""),
                        m.get("status", "PENDING"),
                        m.get("direction"),
                        m.get("sourceReference"),
                        m.get("evidenceId"),
                        m.get("illustrationUrl"),
                        m.get("svgFallback", ""),
                        1 if m.get("isAiGenerated") else 0,
                        m.get("aiLabel", "Vector Illustration"),
                        m.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        json.dumps(m.get("technicalDetails", {})),
                    ),
                )
        conn.close()

    def get_task_passport(self, task_id: str) -> Optional[Dict[str, Any]]:
        conn = get_sqlite_conn()
        p_row = conn.execute(
            "SELECT * FROM task_passports WHERE task_id = ?", (task_id,)
        ).fetchone()
        if not p_row:
            conn.close()
            return None

        m_rows = conn.execute(
            "SELECT * FROM passport_milestones WHERE task_id = ? ORDER BY step_index ASC",
            (task_id,),
        ).fetchall()
        conn.close()

        milestones = []
        for r in m_rows:
            milestones.append(
                {
                    "milestoneId": r["milestone_id"],
                    "milestoneType": r["milestone_type"],
                    "stepIndex": r["step_index"],
                    "title": r["title"],
                    "description": r["description"],
                    "status": r["status"],
                    "direction": r["direction"],
                    "sourceReference": r["source_reference"],
                    "evidenceId": r["evidence_id"],
                    "illustrationUrl": r["illustration_url"],
                    "svgFallback": r["svg_fallback"],
                    "isAiGenerated": bool(r["is_ai_generated"]),
                    "aiLabel": r["ai_label"],
                    "timestamp": r["timestamp"],
                    "technicalDetails": json.loads(r["technical_details_json"]),
                }
            )

        return {
            "taskId": p_row["task_id"],
            "goal": p_row["goal"],
            "workflowMode": p_row["workflow_mode"],
            "sourceToTarget": p_row["source_to_target"],
            "verificationStatus": p_row["verification_status"],
            "totalMilestones": p_row["total_milestones"],
            "summaryNotice": p_row["summary_notice"],
            "provenanceSha256": p_row["provenance_sha256"],
            "milestones": milestones,
            "visualStorytellingEnabled": settings.enable_visual_storytelling,
        }

    # --- Artifacts ---
    def record_artifact(
        self,
        artifact_id: str,
        task_id: str,
        file_path: str,
        prompt_hash: Optional[str] = None,
        file_size_bytes: int = 0,
        artifact_type: str = "image",
    ) -> None:
        conn = get_sqlite_conn()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO artifacts (artifact_id, task_id, artifact_type, file_path, prompt_hash, file_size_bytes, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    artifact_id,
                    task_id,
                    artifact_type,
                    file_path,
                    prompt_hash,
                    file_size_bytes,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        conn.close()

    def deactivate_task_artifacts(self, task_id: str) -> int:
        conn = get_sqlite_conn()
        with conn:
            cur = conn.execute(
                """
                UPDATE artifacts
                SET is_active = 0, deleted_at = ?
                WHERE task_id = ? AND is_active = 1
                """,
                (datetime.now(timezone.utc).isoformat(), task_id),
            )
            count = cur.rowcount
            # Also clear illustration URLs in passport_milestones
            conn.execute(
                """
                UPDATE passport_milestones
                SET illustration_url = NULL, is_ai_generated = 0, ai_label = 'Vector Illustration'
                WHERE task_id = ?
                """,
                (task_id,),
            )
        conn.close()
        return count

    # --- Web Research ---
    def save_web_research(
        self,
        research_id: str,
        query: str,
        provider: str,
        results: list,
        citations: list,
    ) -> None:
        conn = get_sqlite_conn()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO web_research (research_id, query, provider, timestamp, results_json, citations_json, status)
                VALUES (?, ?, ?, ?, ?, ?, 'COMPLETED')
                """,
                (
                    research_id,
                    query,
                    provider,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(results),
                    json.dumps(citations),
                ),
            )
        conn.close()

    def get_web_research(self, research_id: str) -> Optional[Dict[str, Any]]:
        conn = get_sqlite_conn()
        row = conn.execute(
            "SELECT * FROM web_research WHERE research_id = ?", (research_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "researchId": row["research_id"],
            "query": row["query"],
            "provider": row["provider"],
            "timestamp": row["timestamp"],
            "results": json.loads(row["results_json"]),
            "citations": json.loads(row["citations_json"]),
            "status": row["status"],
        }

    # Backward-compatible method aliases
    save_source_reference = save_source
    get_source_reference = get_source
    save_context_fact = save_fact
    get_context_facts_for_source = get_facts_for_source
    save_evidence_reference = save_evidence
    get_evidence_records_for_task = get_evidence_for_task


# Global durable storage singleton
durable_storage = DurableStorage()
