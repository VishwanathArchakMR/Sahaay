"""Retrieval engine for authorized sources and facts."""

from typing import List, Optional
from uuid import UUID

from sahaay_core.context.store import ContextStore
from sahaay_core.contracts.models import ContextFact
from sahaay_core.sources.manager import SourceManager


class ScopedRetriever:
    """Retrieves relevant facts and sources while strictly enforcing authorization scopes."""

    def __init__(self, source_manager: SourceManager, context_store: ContextStore) -> None:
        self.source_manager = source_manager
        self.context_store = context_store

    def retrieve_context_for_query(
        self,
        query: str,
        permitted_source_ids: Optional[List[UUID]] = None,
    ) -> List[ContextFact]:
        """Retrieve facts matching query from permitted sources only."""
        results: List[ContextFact] = []
        active_sources = {s.sourceId for s in self.source_manager.list_active_sources()}

        # Filter by requested permitted sources if supplied
        allowed_source_ids = active_sources
        if permitted_source_ids is not None:
            allowed_source_ids = active_sources.intersection(set(permitted_source_ids))

        for source_id in allowed_source_ids:
            facts = self.context_store.get_facts_for_source(source_id)
            query_lower = query.lower()
            for fact in facts:
                if query_lower in fact.content.lower():
                    results.append(fact)

        return results
