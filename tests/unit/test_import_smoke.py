"""Import smoke test verifying that all core modules, adapters, routers, and contracts

can be cleanly imported without unresolved dependency errors.
"""


def test_core_contracts_and_config_imports():
    from sahaay_core.config.settings import Settings, settings
    from sahaay_core.contracts.models import (
        ActionTypeEnum,
        TaskStatusEnum,
    )

    assert settings is not None
    assert isinstance(settings, Settings)
    assert TaskStatusEnum.OBSERVING.value == "OBSERVING"
    assert ActionTypeEnum.SET_CONTROL_TEXT.value == "set_control_text"


def test_model_adapters_imports():
    from sahaay_core.models.local.llama_runtime import local_llama_manager
    from sahaay_core.models.meta.muse_image import MuseImageClient, muse_image
    from sahaay_core.models.meta.muse_spark import MuseSparkClient, muse_spark

    assert muse_spark is not None
    assert isinstance(muse_spark, MuseSparkClient)
    assert muse_image is not None
    assert isinstance(muse_image, MuseImageClient)
    assert local_llama_manager is not None


def test_core_services_and_api_routers_imports():
    from sahaay_core.api.v1.storytelling import router as storytelling_router
    from sahaay_core.api.v1.workflows import router as workflows_router
    from sahaay_core.ledger.evidence_ledger import EvidenceLedger
    from sahaay_core.main import app
    from sahaay_core.orchestration.orchestrator import TaskOrchestrator
    from sahaay_core.policy.action_gate import ActionGate

    assert app is not None
    assert storytelling_router is not None
    assert workflows_router is not None
    assert ActionGate is not None
    assert EvidenceLedger is not None
    assert TaskOrchestrator is not None
