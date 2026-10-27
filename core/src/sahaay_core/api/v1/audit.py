"""Audit and Evidence Ledger Endpoints."""

from typing import List
from uuid import UUID

from fastapi import APIRouter

from sahaay_core.api.v1.actions import evidence_ledger
from sahaay_core.contracts.models import EvidenceReference

router = APIRouter(prefix="/audit", tags=["Audit & Evidence"])


@router.get("/evidence/task/{task_id}", response_model=List[EvidenceReference])
async def get_task_evidence(task_id: UUID) -> List[EvidenceReference]:
    """Retrieve immutable evidence records linking actions to verified states."""
    return evidence_ledger.get_evidence_for_task(task_id)
