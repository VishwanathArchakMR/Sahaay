"""Tests for Source Registry and Context Retrieval."""

from uuid import uuid4

from sahaay_core.context.store import ContextStore
from sahaay_core.contracts.models import FactTypeEnum
from sahaay_core.retrieval.retriever import ScopedRetriever
from sahaay_core.sources.manager import SourceManager


def test_source_revocation_fails_closed():
    manager = SourceManager()
    source = manager.register_source(
        source_type="local_file",
        uri="C:\\data\\financials.pdf",
        title="Q3 Financials",
    )
    assert manager.is_source_permitted(source.sourceId) is True

    # Revoke source
    manager.revoke_source(source.sourceId)
    assert manager.is_source_permitted(source.sourceId) is False
    assert manager.get_source(source.sourceId) is None


def test_scoped_retrieval_respects_revocation():
    manager = SourceManager()
    store = ContextStore()
    retriever = ScopedRetriever(source_manager=manager, context_store=store)

    s1 = manager.register_source(source_type="local_file", uri="C:\\data\\s1.txt")
    s2 = manager.register_source(source_type="local_file", uri="C:\\data\\s2.txt")

    f1 = store.record_fact(
        fact_type=FactTypeEnum.SOURCE_EXTRACTED,
        content="Revenue grew by 24% in Q3",
        source_reference_id=s1.sourceId,
    )
    assert f1.factId is not None
    f2 = store.record_fact(
        fact_type=FactTypeEnum.SOURCE_EXTRACTED,
        content="Operating costs grew by 10% in Q3",
        source_reference_id=s2.sourceId,
    )

    # Initial query finds both
    results = retriever.retrieve_context_for_query("grew")
    assert len(results) == 2

    # Revoking s1 immediately hides f1 from subsequent retrieval
    manager.revoke_source(s1.sourceId)
    results_after_revocation = retriever.retrieve_context_for_query("grew")
    assert len(results_after_revocation) == 1
    assert results_after_revocation[0].factId == f2.factId


def test_derivation_chain_provenance():
    store = ContextStore()
    source_id = uuid4()

    # Fact 1: extracted from source
    f1 = store.record_fact(
        fact_type=FactTypeEnum.SOURCE_EXTRACTED,
        content="User clicks login button",
        source_reference_id=source_id,
    )

    # Fact 2: derived from Fact 1
    f2 = store.record_fact(
        fact_type=FactTypeEnum.INFERRED,
        content="User intended to authenticate",
        source_reference_id=source_id,
        derivation_ids=[f1.factId],
    )

    chain = store.get_derivation_chain(f2.factId)
    assert len(chain) == 2
    assert chain[0].factId == f2.factId
    assert chain[1].factId == f1.factId
