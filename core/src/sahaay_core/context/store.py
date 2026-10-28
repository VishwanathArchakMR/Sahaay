"""Context Store and Provenance Ledger for Sahaay.

Maintains structured facts, source links, derivation relationships, and classification.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sahaay_core.contracts.models import ContextFact, FactTypeEnum
from sahaay_core.storage.persistence import durable_storage


class ContextStore:
    """Manages facts with explicit provenance and derivation trees backed by SQLite."""

    def __init__(self) -> None:
        self._facts: Dict[UUID, ContextFact] = {}

    def record_fact(
        self,
        fact_type: FactTypeEnum,
        content: str,
        source_reference_id: UUID,
        derivation_ids: Optional[List[UUID]] = None,
        confidence_score: float = 1.0,
        metadata: Optional[Dict] = None,
    ) -> ContextFact:
        """Record a structured fact tied to a verified source and persist it."""
        fact = ContextFact(
            factId=uuid4(),
            factType=fact_type,
            content=content,
            sourceReferenceId=source_reference_id,
            derivationIds=derivation_ids or [],
            confidenceScore=confidence_score,
            recordedAt=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        durable_storage.save_fact(fact)
        self._facts[fact.factId] = fact
        return fact

    def get_fact(self, fact_id: UUID) -> Optional[ContextFact]:
        """Fetch a specific fact by ID from cache or durable persistence."""
        fact = self._facts.get(fact_id)
        if not fact:
            fact = durable_storage.get_fact(fact_id)
            if fact:
                self._facts[fact_id] = fact
        return fact

    def get_facts_for_source(self, source_reference_id: UUID) -> List[ContextFact]:
        """Retrieve all facts originating from a specific source, checking cache or durable storage."""
        in_mem = [f for f in self._facts.values() if f.sourceReferenceId == source_reference_id]
        if in_mem:
            return in_mem
        db_facts = durable_storage.get_facts_for_source(source_reference_id)
        for f in db_facts:
            self._facts[f.factId] = f
        return db_facts

    def get_derivation_chain(self, fact_id: UUID) -> List[ContextFact]:
        """Trace lineage of derived facts back to source observations."""
        chain: List[ContextFact] = []
        fact = self.get_fact(fact_id)
        if not fact:
            return chain

        chain.append(fact)
        for parent_id in fact.derivationIds:
            chain.extend(self.get_derivation_chain(parent_id))
        return chain
