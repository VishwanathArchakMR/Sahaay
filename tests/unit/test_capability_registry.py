"""Unit tests for the central Capability Registry and its planner integration."""

from sahaay_core.capabilities import capability_registry
from sahaay_core.capabilities.models import CapabilityReadiness, RiskCategory
from sahaay_core.models.meta.muse_spark import (
    MuseSparkClient,
    PlanStepProposal,
    StructuredTaskPlan,
)


def test_registry_contains_implemented_capabilities():
    """Authoritative registry contains all 12 currently implemented capabilities."""
    caps = capability_registry.list_capabilities()
    assert len(caps) >= 12

    cap_ids = {c.capability_id for c in caps}
    expected = {
        "browser_tab_observe",
        "browser_fill_form",
        "browser_get_values",
        "windows_set_control_text",
        "windows_get_control_text",
        "windows_inspect_window",
        "document_ingest_chunk",
        "deterministic_retrieval",
        "verify_readback",
        "user_authorization",
        "research_web_search",
        "research_fetch_page",
    }
    assert expected.issubset(cap_ids)


def test_capability_descriptors_have_complete_contracts():
    """Every capability descriptor must specify preconditions, permissions, risk, and schemas."""
    for cap in capability_registry.list_capabilities():
        assert cap.capability_id
        assert cap.name
        assert cap.description
        assert len(cap.supported_surfaces) > 0
        assert cap.adapter
        assert isinstance(cap.risk_category, RiskCategory)
        assert isinstance(cap.readiness_state, CapabilityReadiness)
        assert isinstance(cap.required_permission_scopes, list)
        assert isinstance(cap.preconditions, list)
        assert isinstance(cap.input_schema, dict)
        assert isinstance(cap.output_schema, dict)


def test_validate_plan_step_success_and_failure():
    """Validation checks registered ID and schema parameters."""
    # Valid invocation
    valid, err = capability_registry.validate_plan_step(
        "browser_fill_form",
        {"fields": {"name": "Test User"}},
    )
    assert valid is True
    assert err is None

    # Nonexistent capability
    valid, err = capability_registry.validate_plan_step(
        "arbitrary.shell.execute",
        {"command": "rm -rf /"},
    )
    assert valid is False
    assert err is not None and "not registered" in err.lower()


def test_registry_generates_catalog_for_prompt():
    """Catalog string for planning prompts must contain registered capability IDs."""
    catalog = capability_registry.get_catalog_for_prompt()
    assert "research_web_search" in catalog
    assert "windows_set_control_text" in catalog
    assert "browser_tab_observe" in catalog
    assert "verify_readback" in catalog


def test_planner_validates_plan_against_capability_registry():
    """Meta Muse Spark planner must validate proposed steps against authoritative registry."""
    planner = MuseSparkClient()

    # Plan with unregistered malicious action must be rejected by semantic policy
    malicious_plan = StructuredTaskPlan(
        task_goal="Hack system",
        workflow_mode="action_only",
        steps=[
            PlanStepProposal(
                step_id="step-1",
                title="Execute root command",
                purpose="gain access",
                capability="system_shell_unrestricted",
                action_type="set_control_text",
                target_surface="desktop_window",
                target_scope="cmd.exe",
                preconditions=[],
                expected_postconditions=[],
                requires_human_approval=True,
                parameters={"cmd": "whoami"},
            )
        ],
    )
    is_valid = planner._validate_semantic_policy(malicious_plan)
    assert is_valid is False
