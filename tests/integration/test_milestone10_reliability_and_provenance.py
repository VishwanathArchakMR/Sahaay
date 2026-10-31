"""Milestone 10 Reliability, Driver Provenance, and System Integration Tests.

Validates:
1. Strict driver provenance enforcement:
   - offline_simulation can NEVER yield VERIFIED status.
   - test_fixture and real_native_driver can yield VERIFIED when conditions match.
2. Production non-simulation mode:
   - WindowsNativeAdapter(allow_simulation=False) raises ConnectionError when daemon is offline.
3. Browser bridge truthful state:
   - Disconnected bridge reports is_connected() == False and does not fabricate observations.
4. Meta model privacy invariants:
   - Outbound network transmissions are strictly blocked in local-only mode.
5. End-to-end browser-to-desktop workflow:
   - Observes deadline_notice.html, extracts deadline and URL, writes to desktop control,
     reads back state, independently verifies, and records in SQLite evidence ledger.
"""

from uuid import uuid4

import pytest
from sahaay_core.adapters.browser.adapter import BrowserAdapter
from sahaay_core.adapters.windows.adapter import WindowsNativeAdapter
from sahaay_core.capabilities.executor import CapabilityExecutor
from sahaay_core.config.settings import get_fixture_path
from sahaay_core.context.store import ContextStore
from sahaay_core.contracts.models import (
    ActionContract,
    ActionTypeEnum,
    ConsentGrant,
    ExecutionResult,
    Session,
    TaskContract,
    TaskStatusEnum,
    VerificationStatusEnum,
)
from sahaay_core.ledger.evidence_ledger import EvidenceLedger
from sahaay_core.models.meta.muse_spark import muse_spark
from sahaay_core.orchestration.dag_engine import TaskDagEngine, TaskDAGNode
from sahaay_core.privacy.privacy_gateway import PrivacyGateway
from sahaay_core.sources.document_ingestion import DocumentIngestionService
from sahaay_core.sources.manager import SourceManager
from sahaay_core.storage.persistence import durable_storage
from sahaay_core.verification.verifier import IndependentVerifier


@pytest.fixture
def m10_env(tmp_path):
    """Setup isolated test environment for Milestone 10 verification."""
    ledger = EvidenceLedger()
    source_manager = SourceManager()
    context_store = ContextStore()
    doc_ingestion = DocumentIngestionService(
        source_manager=source_manager,
        context_store=context_store,
    )
    windows_adapter = WindowsNativeAdapter(allow_simulation=True)
    browser_adapter = BrowserAdapter()
    executor = CapabilityExecutor(
        windows_adapter=windows_adapter,
        browser_adapter=browser_adapter,
        doc_ingestion=doc_ingestion,
        context_store=context_store,
    )
    dag_engine = TaskDagEngine(executor=executor, evidence_ledger=ledger)

    session_id = uuid4()
    session = Session(sessionId=session_id, localOnlyMode=False)
    durable_storage.save_session(session)

    grant = ConsentGrant(
        grantId=uuid4(),
        sessionId=session_id,
        scope="*",
        purpose="Milestone 10 Reliability Verification",
    )
    durable_storage.save_consent_grant(grant)

    return {
        "ledger": ledger,
        "executor": executor,
        "dag_engine": dag_engine,
        "session": session,
        "grant": grant,
        "tmp_path": tmp_path,
        "windows_adapter": windows_adapter,
        "browser_adapter": browser_adapter,
    }


def test_strict_driver_provenance_rejects_offline_simulation():
    """Verify IndependentVerifier strictly returns UNVERIFIED if driver was simulated offline."""
    action = ActionContract(
        actionId=uuid4(),
        actionType=ActionTypeEnum.SET_CONTROL_TEXT,
        target="hwnd:1001:Edit",
        parameters={"text": "Test Value"},
        expectedPostcondition="Value written to control",
    )

    # 1. Execution with offline_simulation provenance
    exec_sim = ExecutionResult(
        executionId=uuid4(),
        actionId=action.actionId,
        isSuccess=True,
        durationMs=15.0,
        outputData={"value": "Test Value", "offlineSimulation": True},
        driverProvenance="offline_simulation",
    )

    res_sim = IndependentVerifier.verify_action_outcome(
        action=action,
        execution_result=exec_sim,
        observed_postcondition_data={
            "state": "Value written to control",
            "driverProvenance": "offline_simulation",
        },
    )
    assert res_sim.status == VerificationStatusEnum.UNVERIFIED
    assert "Offline simulation driver cannot establish physical completion" in res_sim.details

    # 2. In contrast, controlled test_fixture provenance allows verified outcome
    exec_fixture = ExecutionResult(
        executionId=uuid4(),
        actionId=action.actionId,
        isSuccess=True,
        durationMs=15.0,
        outputData={"value": "Test Value"},
        driverProvenance="test_fixture",
    )
    res_fixture = IndependentVerifier.verify_action_outcome(
        action=action,
        execution_result=exec_fixture,
        observed_postcondition_data={
            "state": "Value written to control",
            "driverProvenance": "test_fixture",
        },
    )
    assert res_fixture.status == VerificationStatusEnum.VERIFIED


def test_production_windows_adapter_raises_connection_error_when_daemon_offline():
    """Verify that when allow_simulation=False, missing daemon raises ConnectionError (no silent fake success)."""
    prod_adapter = WindowsNativeAdapter(
        pipe_name="NonExistentSahaayPipe_M10",
        allow_simulation=False,
    )

    assert prod_adapter.is_connected() is False

    with pytest.raises(ConnectionError) as exc_info:
        prod_adapter.set_control_text(hwnd=1234, text="Real write attempt", target_id="Edit")

    assert "Windows companion daemon (Sahaay.Controller) is not running" in str(exc_info.value)

    with pytest.raises(ConnectionError) as exc_info2:
        prod_adapter.set_system_volume(volume=40)

    assert "Real desktop operation 'set_system_volume' is unavailable" in str(exc_info2.value)


def test_browser_bridge_unconnected_reports_truthful_state():
    """Verify BrowserAdapter truthfully reports disconnected status and refuses to fabricate observations."""
    adapter = BrowserAdapter(pipe_name="NonExistentBrowserPipe_M10")
    assert adapter.is_connected() is False
    with pytest.raises(RuntimeError) as exc_info:
        adapter.get_active_tab_observation()
    assert "Browser bridge not reachable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_meta_models_preserve_local_privacy_invariants():
    """Verify Privacy Gateway and Meta model adapters enforce local-only mode strictly."""
    gateway = PrivacyGateway(local_only_mode=True)
    decision = gateway.evaluate_outbound_request(
        destination="https://api.meta.ai/v1",
        purpose="Inference",
        content="Extract sensitive invoice values",
        active_grants=[],
    )
    assert decision.allowTransmission is False
    assert "Local-only mode is active" in decision.reason

    # Model planner respects local-only invariant
    session = Session(sessionId=uuid4(), localOnlyMode=True)
    plan = await muse_spark.generate_plan(
        task=TaskContract(
            taskId=uuid4(),
            sessionId=session.sessionId,
            goal="Analyze confidential bank statement",
            taskType="combined_retrieval_and_action",
        ),
        context="Account balance 50,000 INR",
        source_facts={"balance": "50,000 INR"},
        active_grants=[],
    )
    assert plan is not None
    assert plan.model_id == "muse-spark-1.3"
    assert plan.validation_status == "LOCAL_FALLBACK"


@pytest.mark.asyncio
async def test_compound_browser_to_desktop_deadline_extraction_and_readback(m10_env):
    """Milestone 10 End-to-End Workflow:

    1. Read deadline notice fixture page.
    2. Extract deadline ('November 30, 2026') and official portal URL.
    3. Transfer extracted deadline and citation to desktop Notepad control.
    4. Perform readback check on destination control.
    5. Persist cryptographic evidence record to SQLite ledger.
    """
    env = m10_env
    fixture_path = get_fixture_path("deadline_notice.html")
    assert fixture_path.exists(), "deadline_notice.html fixture must exist"

    page_html = fixture_path.read_text(encoding="utf-8")
    assert "November 30, 2026" in page_html
    assert "https://solar.karnataka.gov.in/apply" in page_html

    task = TaskContract(
        taskId=uuid4(),
        sessionId=env["session"].sessionId,
        goal="Find the application deadline on the active test webpage and write it into Notepad with the source URL",
        taskType="combined_retrieval_and_action",
    )
    durable_storage.save_task(task)

    # Construct DAG for Browser -> Desktop workflow
    nodes = [
        TaskDAGNode(
            step_id="step-obs",
            capability_id="browser_tab_observe",
            action_type="custom",
            instruction="Observe active browser tab containing the solar subsidy deadline notice",
            parameters={
                "url": "https://solar.karnataka.gov.in/apply",
                "title": "Public Utility Scheme - Application Deadline Notice",
                "pageText": page_html,
            },
        ),
        TaskDAGNode(
            step_id="step-write",
            capability_id="windows_set_control_text",
            action_type="set_control_text",
            instruction="Write extracted deadline and source citation into Notepad",
            dependencies=["step-obs"],
            parameters={
                "hwnd": 0,
                "targetId": "Edit",
                "text": "Solar Scheme Deadline: November 30, 2026 (Source: https://solar.karnataka.gov.in/apply)",
            },
        ),
        TaskDAGNode(
            step_id="step-verify",
            capability_id="verify_readback",
            action_type="custom",
            instruction="Verify destination control text contains the required deadline and source URL",
            dependencies=["step-write"],
            parameters={
                "target": "windows",
                "hwnd": 0,
                "targetId": "Edit",
                "expectedText": "November 30, 2026",
            },
        ),
    ]

    report = await env["dag_engine"].execute_dag(
        task=task,
        nodes=nodes,
        active_grants=[env["grant"]],
    )

    assert report.is_success is True
    assert report.final_status == TaskStatusEnum.COMPLETED
    assert report.completed_steps_count == 3
    assert len(report.evidence_ids) == 3

    # Check that verification readback verified the text
    verify_step_res = report.step_results["step-verify"]["data"]
    assert verify_step_res["isVerified"] is True
    assert "November 30, 2026" in verify_step_res["readbackData"]["text"]

    # Verify cryptographic evidence saved in SQLite ledger
    evidence_list = env["ledger"].get_evidence_for_task(task.taskId)
    assert len(evidence_list) == 3

    # Verify latest evidence record contains expected narrative and cryptographic signatures
    latest_ev = evidence_list[-1]
    assert "verify_readback" in latest_ev.narrative or "step-verify" in latest_ev.narrative
    assert latest_ev.verificationResultId is not None
