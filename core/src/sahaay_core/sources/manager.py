"""Source Registry and Permission Management for Sahaay."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sahaay_core.contracts.models import SourceReference
from sahaay_core.storage.persistence import durable_storage


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
        sha256: Optional[str] = None,
    ) -> SourceReference:
        """Register a new source reference and persist it durably."""
        effective_checksum = checksum or sha256
        source = SourceReference(
            sourceId=uuid4(),
            sourceType=source_type,
            uri=uri,
            observedAt=datetime.now(timezone.utc),
            title=title,
            checksum=effective_checksum,
            metadata=metadata or {},
        )
        durable_storage.save_source(source)
        self._sources[source.sourceId] = source
        return source

    def get_source(self, source_id: UUID | str) -> Optional[SourceReference]:
        """Retrieve source reference if not revoked, checking durable storage if uncached."""
        s_uuid = UUID(str(source_id))
        if s_uuid in self._revoked_source_ids:
            return None
        source = self._sources.get(s_uuid)
        if not source:
            source = durable_storage.get_source(s_uuid)
            if source:
                self._sources[s_uuid] = source
        return source

    def is_source_permitted(self, source_id: UUID | str) -> bool:
        """Verify that source exists and has not been revoked."""
        s_uuid = UUID(str(source_id))
        if s_uuid in self._revoked_source_ids:
            return False
        return self.get_source(s_uuid) is not None

    def revoke_source(self, source_id: UUID | str, reason: Optional[str] = None) -> bool:
        """Revoke authorization for a source; fails closed in durable storage and memory."""
        s_uuid = UUID(str(source_id))
        self._revoked_source_ids.add(s_uuid)
        if s_uuid in self._sources:
            del self._sources[s_uuid]
        return durable_storage.revoke_source(s_uuid)

    def list_active_sources(self) -> List[SourceReference]:
        """List all non-revoked sources, hydrating from durable persistence if cache empty."""
        if not self._sources:
            for s in durable_storage.list_active_sources():
                self._sources[s.sourceId] = s
        return [s for s_id, s in self._sources.items() if s_id not in self._revoked_source_ids]
