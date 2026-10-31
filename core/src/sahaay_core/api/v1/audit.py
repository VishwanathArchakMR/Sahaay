"""Audit and Evidence Ledger Endpoints."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter

from sahaay_core.api.v1.actions import evidence_ledger
from sahaay_core.config.logging import get_log_dir
from sahaay_core.contracts.models import EvidenceReference

router = APIRouter(prefix="/audit", tags=["Audit & Evidence"])


@router.get("/evidence/task/{task_id}", response_model=List[EvidenceReference])
async def get_task_evidence(task_id: UUID) -> List[EvidenceReference]:
    """Retrieve immutable evidence records linking actions to verified states."""
    return evidence_ledger.get_evidence_for_task(task_id)


@router.get("/logs")
async def get_system_logs(
    limit: int = 100,
    error_only: bool = False,
    component: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve latest sanitized log entries across local application log streams."""
    log_dir = get_log_dir()
    log_file = log_dir / "backend.log"
    entries: List[Dict[str, Any]] = []

    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            for line in reversed(lines[-500:]):
                line = line.strip()
                if not line:
                    continue
                # Format: 2026-10-31 22:50:00 [INFO] [sahaay.component] [-] message
                parts = line.split(" ", 4)
                if len(parts) >= 5:
                    ts = f"{parts[0]} {parts[1]}"
                    lvl = parts[2].strip("[]")
                    cmp = parts[3].strip("[]")
                    msg = parts[4]
                    if error_only and lvl not in ("ERROR", "CRITICAL", "WARNING"):
                        continue
                    if component and component.lower() not in cmp.lower():
                        continue
                    entries.append({
                        "timestamp": ts,
                        "level": lvl,
                        "component": cmp,
                        "message": msg,
                    })
                    if len(entries) >= limit:
                        break
        except Exception:
            pass

    return {
        "logDirectory": str(log_dir),
        "total": len(entries),
        "entries": entries,
    }
