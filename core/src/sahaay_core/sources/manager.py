"""Source Registry and Permission Management for Sahaay."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sahaay_core.contracts.models import SourceReference


class SourceManager:
    """Manages permitted sources (files, browser tabs, windows) and verifies authorization."""

    def __init__(self) -> None:
        self._sources: Dict[UUID, SourceReference] = {}
        self._revoked_source_ids: set[UUID] = set()

    def register_source(
        self,
        source_type: str,
        uri: str,
        title: Optional[str] = None,
        checksum: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> SourceReference:
        """Register a new source reference."""
        source = SourceReference(
            sourceId=uuid4(),
            sourceType=source_type,
            uri=uri,
            observedAt=datetime.now(timezone.utc),
            title=title,
            checksum=checksum,
            metadata=metadata or {},
        )
        self._sources[source.sourceId] = source
        return source

    def get_source(self, source_id: UUID) -> Optional[SourceReference]:
        """Retrieve source reference if not revoked."""
        if source_id in self._revoked_source_ids:
            return None
        return self._sources.get(source_id)

    def is_source_permitted(self, source_id: UUID) -> bool:
        """Verify that source exists and has not been revoked."""
        if source_id in self._revoked_source_ids:
            return False
        return source_id in self._sources

    def revoke_source(self, source_id: UUID) -> bool:
        """Revoke authorization for a source; fails closed for future reads."""
        if source_id in self._sources:
            self._revoked_source_ids.add(source_id)
            return True
        return False

    def list_active_sources(self) -> List[SourceReference]:
        """List all non-revoked sources."""
        return [s for s_id, s in self._sources.items() if s_id not in self._revoked_source_ids]
