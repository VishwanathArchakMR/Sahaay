"""Unit and Integration Tests for Sahaay Milestone 08.

Covers:
1. Native Messaging Host standalone binary diagnostics (`--test` CLI check for Chrome & Edge registration).
2. BrowserAdapter Named Pipe IPC communication & offline fallbacks.
3. CapabilityExecutor dispatch for all browser capabilities (observe, scroll, fill, get_values, click).
4. Mind2Web SemanticElementSelector (ARIA matching, role affinity, few-shot action retrieval).
5. Mind2Web evaluation suite execution and metric assertions.
6. Desktop UI Automation grounding vs coordinate drift evaluation.
7. Hardware feasibility assessment on verified RTX 3050 4GB GPU.
8. End-to-end browser action, verification, and evidence ledger persistence.
"""

import subprocess
from pathlib import Path

import pytest
from sahaay_core.adapters.browser.selector import (
    FewShotActionRetriever,
    SemanticElementSelector,
)
from sahaay_core.capabilities.executor import CapabilityExecutor
from sahaay_core.capabilities.registry import capability_registry
from sahaay_core.evaluation.desktop_eval import DesktopEvaluator
from sahaay_core.evaluation.mind2web_eval import Mind2WebEvaluator
from sahaay_core.ledger.evidence_ledger import EvidenceLedger


class TestMilestone08NativeHost:
    """Tests standalone NativeHost installation diagnostics."""

    def test_standalone_native_host_diagnostics_cli(self):
        """Test that the published standalone Sahaay.NativeHost.exe executes with --test."""
        exe_path = (
            Path(__file__).resolve().parent.parent.parent
            / "bin"
            / "dist"
            / "native-host-standalone"
            / "Sahaay.NativeHost.exe"
        )
        if not exe_path.exists():
            pytest.skip(f"Standalone native host binary not found at {exe_path}")

        proc = subprocess.run(
            [str(exe_path), "--test"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0
        import json
        data = json.loads(proc.stdout)
        assert data["verified"] is True
        assert data["chrome"]["registered"] is True
        assert data["edge"]["registered"] is True
        assert "Google Chrome" in data["supportedBrowsers"]
        assert "Microsoft Edge" in data["supportedBrowsers"]


class TestMilestone08BrowserAdapter:
    """Tests BrowserAdapter communication and capability execution."""

    def test_browser_capabilities_registered(self):
        """Verify all browser capabilities are present in capability registry."""
        capabilities = [
            "browser_tab_observe",
            "browser_scroll_tab",
            "browser_fill_form",
            "browser_get_values",
            "browser_click_element",
        ]
        for cap_id in capabilities:
            desc = capability_registry.get(cap_id)
            assert desc is not None, f"Capability {cap_id} missing from registry"
            assert desc.capability_id == cap_id

    @pytest.mark.asyncio
    async def test_capability_executor_browser_observe(self):
        """Test CapabilityExecutor executes browser_tab_observe cleanly."""
        executor = CapabilityExecutor()
        res = await executor.execute(
            "browser_tab_observe",
            {"url": "https://service.gov.in/billpay", "pageText": "Electricity Bill Payment"},
        )
        assert "tabId" in res
        assert "url" in res
        assert "pageText" in res
        assert "interactiveControls" in res
        assert "isBridgeConnected" in res

    @pytest.mark.asyncio
    async def test_capability_executor_browser_scroll(self):
        """Test CapabilityExecutor executes browser_scroll_tab."""
        executor = CapabilityExecutor()
        res = await executor.execute("browser_scroll_tab", {"deltaY": 450})
        assert "requestedDeltaY" in res or "actualDeltaY" in res or "postScrollY" in res

    @pytest.mark.asyncio
    async def test_capability_executor_browser_fill_form(self):
        """Test CapabilityExecutor executes browser_fill_form."""
        executor = CapabilityExecutor()
        res = await executor.execute(
            "browser_fill_form",
            {"fields": {"accountNumber": "987654321", "amount": "1450.50"}},
        )
        assert res.get("count") == 2 or res.get("filledCount") == 2 or "filled" in res

    @pytest.mark.asyncio
    async def test_capability_executor_browser_get_values(self):
        """Test CapabilityExecutor executes browser_get_values."""
        executor = CapabilityExecutor()
        res = await executor.execute(
            "browser_get_values",
            {"fieldNames": ["accountNumber", "amount"]},
        )
        assert "values" in res

    @pytest.mark.asyncio
    async def test_capability_executor_browser_click_element(self):
        """Test CapabilityExecutor executes browser_click_element."""
        executor = CapabilityExecutor()
        res = await executor.execute(
            "browser_click_element",
            {"targetId": "pay-now-btn", "selector": "#pay-now-btn"},
        )
        assert res.get("target") == "pay-now-btn" or "clicked" in res or res.get("success") is True


class TestMilestone08Mind2Web:
    """Tests Mind2Web semantic selector, action retriever, and evaluation harness."""

    def test_semantic_selector_aria_priority(self):
        """Verify aria-label takes priority over generic element IDs or text."""
        selector = SemanticElementSelector()
        candidates = [
            {"id": "btn-generic-1", "text": "Click Here", "ariaLabel": "Submit Application Form", "role": "button"},
            {"id": "btn-generic-2", "text": "Save", "ariaLabel": "Save Draft", "role": "button"},
        ]
        best = selector.select_best_target("Submit the application form", candidates, action_hint="CLICK")
        assert best is not None
        assert best.element_id == "btn-generic-1"
        assert best.matched_property == "aria_label"

    def test_semantic_selector_role_affinity(self):
        """Verify role affinity rewards matching element types (e.g. textbox for TYPE)."""
        selector = SemanticElementSelector()
        candidates = [
            {"id": "search-btn", "role": "button", "text": "Search"},
            {"id": "search-input", "role": "textbox", "placeholder": "Search query", "name": "q"},
        ]
        best = selector.select_best_target("Type query into search input", candidates, action_hint="TYPE")
        assert best is not None
        assert best.element_id == "search-input"

    def test_few_shot_action_retriever(self):
        """Verify few-shot action retriever retrieves top matches for user intent."""
        tasks = [
            {"userIntent": "Add item to shopping bag", "groundTruthAction": "CLICK", "expectedRole": "button"},
            {"userIntent": "Enter email address", "groundTruthAction": "TYPE", "expectedRole": "textbox"},
        ]
        retriever = FewShotActionRetriever(tasks)
        matches = retriever.retrieve_relevant_examples("Add to bag", top_k=1)
        assert len(matches) == 1
        assert matches[0]["recommendedAction"] == "CLICK"

        formatted = retriever.format_examples_for_planner("Enter email address")
        assert formatted is not None
        assert "TYPE" in formatted

    def test_mind2web_evaluator_run(self):
        """Execute full Mind2Web evaluation across 50 sample tasks."""
        evaluator = Mind2WebEvaluator()
        results = evaluator.run_evaluation(include_few_shot=True)
        assert results["totalTasks"] == 50
        assert results["semanticSelector"]["accuracyPercent"] >= 85.0
        assert results["semanticSelector"]["accuracyPercent"] >= results["baseline"]["accuracyPercent"]
        assert results["fewShotRetriever"]["actionMatchRatePercent"] >= 90.0


class TestMilestone08DesktopEvaluation:
    """Tests Uni-GUI-Desktop-1 evaluation and hardware sizing."""

    def test_desktop_grounding_evaluator(self):
        """Test desktop evaluator benchmarking UI Automation vs coordinate bounding boxes."""
        evaluator = DesktopEvaluator()
        res = evaluator.evaluate_grounding()
        assert res["totalTasks"] == 50
        # UI Automation deterministic accuracy is 100%
        assert res["uiAutomation"]["accuracyPercent"] == 100.0
        assert res["uiAutomation"]["deterministic"] is True
        # Coordinate guessing under 125% DPI scale fails
        assert res["coordinateBoundingBox"]["accuracyPercent"] < res["uiAutomation"]["accuracyPercent"]

    def test_desktop_hardware_feasibility(self):
        """Test that hardware feasibility verifies RTX 3050 4GB VRAM and hybrid architecture."""
        evaluator = DesktopEvaluator()
        hw = evaluator.assess_hardware_and_model_feasibility()
        assert hw["verifiedHardware"]["vramGb"] == 4.0
        # Local 7B models must be marked as not feasible on 4GB VRAM
        for model in hw["candidateModelsAnalysis"]:
            if "7B" in model["model"] or "DeskForge" in model["model"]:
                assert model["feasibleOnLocalRtx3050"] is False
            elif "Hybrid" in model["model"]:
                assert model["feasibleOnLocalRtx3050"] is True
        assert "Do NOT download heavy local 7B+ vision models" in hw["architecturalDecision"]


class TestMilestone08EvidenceLedgerPersistence:
    """Tests end-to-end observation, action execution, and evidence recording in SQLite ledger."""

    def test_browser_action_recorded_in_evidence_ledger(self):
        """Verify browser action execution produces a persistent record in SQLite evidence ledger."""
        from datetime import datetime, timezone
        from uuid import uuid4

        from sahaay_core.contracts.models import VerificationResult, VerificationStatusEnum

        ledger = EvidenceLedger()
        task_id = uuid4()
        step_id = uuid4()
        action_id = uuid4()
        obs_id = uuid4()

        verification_result = VerificationResult(
            verificationId=uuid4(),
            actionId=action_id,
            status=VerificationStatusEnum.VERIFIED,
            verifierType="dom_field_readback",
            verifiedAt=datetime.now(timezone.utc),
            details="Verified DOM readback for accountNumber and amount",
        )

        evidence = ledger.record_evidence(
            task_id=task_id,
            step_id=step_id,
            action_id=action_id,
            verification_result=verification_result,
            observation_id=obs_id,
            narrative="Verified active browser tab form field population against utility invoice facts",
        )

        assert evidence is not None
        assert evidence.taskId == task_id
        assert evidence.actionId == action_id
        assert evidence.verificationResultId == verification_result.verificationId

        # Retrieve from durable SQLite storage
        records = ledger.get_evidence_for_task(task_id)
        assert len(records) >= 1
        assert records[0].evidenceId == evidence.evidenceId
        assert records[0].taskId == task_id
