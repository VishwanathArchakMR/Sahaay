"""Evidence Ledger for Sahaay.

Immutable record tying every step, observation, action, policy decision, execution result,
and independent verification state together.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sahaay_core.contracts.models import (
    EvidenceReference,
    VerificationResult,
)
from sahaay_core.storage.persistence import durable_storage


class EvidenceLedger:
    """Stores immutable audit and evidence references for all task actions in SQLite."""

    def __init__(self) -> None:
        self._records: Dict[UUID, EvidenceReference] = {}

    def record_evidence(
        self,
        task_id: UUID,
        step_id: UUID,
        action_id: UUID,
        verification_result: VerificationResult,
        observation_id: Optional[UUID] = None,
        narrative: str = "",
    ) -> EvidenceReference:
        """Create an evidence record linking an action to its verified outcome and persist it."""
        evidence = EvidenceReference(
            evidenceId=uuid4(),
            taskId=task_id,
            stepId=step_id,
            actionId=action_id,
            observationId=observation_id,
            verificationResultId=verification_result.verificationId,
            createdAt=datetime.now(timezone.utc),
            narrative=narrative or f"Verification outcome: {verification_result.status.value}",
        )
        durable_storage.save_evidence(evidence)
        self._records[evidence.evidenceId] = evidence
        return evidence

    def get_evidence_for_task(self, task_id: UUID) -> List[EvidenceReference]:
        """Fetch all evidence recorded for a task from durable storage."""
        return durable_storage.get_evidence_for_task(task_id)
