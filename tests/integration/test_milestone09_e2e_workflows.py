"""Milestone 09 End-to-End Integration Tests.

Validates complete real end-to-end task execution across the unified Sahaay architecture:
- Workflow A: Information retrieval, source citation, and persistent evidence ledger.
- Workflow B: Browser tab retrieval, cross-surface transfer, destination readback, and verification.
- Workflow C: Compound DAG task with dependency ordering, fact propagation, and failure safety.
- Workflow D: Windows application allowlist, UI Automation, and native system controls.
- Workflow E: Retrieval-only non-mutation invariant enforcement by Action Gate.
"""

from uuid import uuid4

import pytest
from sahaay_core.adapters.browser.adapter import BrowserAdapter
from sahaay_core.adapters.windows.adapter import WindowsNativeAdapter
from sahaay_core.capabilities.executor import CapabilityExecutor
from sahaay_core.context.store import ContextStore
from sahaay_core.contracts.models import (
    ActionContract,
    ActionTypeEnum,
    ConsentGrant,
    ExecutionResult,
    PolicyDecisionEnum,
    Session,
    TaskContract,
    TaskStatusEnum,
    VerificationStatusEnum,
)
from sahaay_core.ledger.evidence_ledger import EvidenceLedger
from sahaay_core.orchestration.dag_engine import TaskDagEngine, TaskDAGNode
from sahaay_core.policy.action_gate import ActionGate
from sahaay_core.sources.document_ingestion import DocumentIngestionService
from sahaay_core.sources.manager import SourceManager
from sahaay_core.storage.persistence import durable_storage
from sahaay_core.verification.verifier import IndependentVerifier


@pytest.fixture
def e2e_environment(tmp_path):
    """Sets up clean isolated components backed by durable persistence."""
    source_manager = SourceManager()
    context_store = ContextStore()
    doc_ingestion = DocumentIngestionService(source_manager, context_store)
    windows_adapter = WindowsNativeAdapter()
    browser_adapter = BrowserAdapter()
    ledger = EvidenceLedger()

    executor = CapabilityExecutor(
        windows_adapter=windows_adapter,
        browser_adapter=browser_adapter,
        doc_ingestion=doc_ingestion,
        source_manager=source_manager,
        context_store=context_store,
    )

    dag_engine = TaskDagEngine(executor=executor, evidence_ledger=ledger)

    session_id = uuid4()
    session = Session(sessionId=session_id, localOnlyMode=True)
    durable_storage.save_session(session)

    grant = ConsentGrant(
        grantId=uuid4(),
        sessionId=session_id,
        scope="*",
        purpose="Milestone 09 E2E Verification",
    )
    durable_storage.save_consent_grant(grant)

    return {
        "tmp_path": tmp_path,
        "source_manager": source_manager,
        "context_store": context_store,
        "doc_ingestion": doc_ingestion,
        "windows_adapter": windows_adapter,
        "browser_adapter": browser_adapter,
        "executor": executor,
        "ledger": ledger,
        "dag_engine": dag_engine,
        "session": session,
        "grant": grant,
    }


# ===========================================================================
# WORKFLOW A: Retrieve Information & Cite Source
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_a_retrieve_and_cite_report(e2e_environment):
    """Workflow A: Find latest report, extract findings, cite exact source, persist evidence."""
    env = e2e_environment
    report_file = env["tmp_path"] / "Project_Report_Q3.txt"
    report_content = (
        "Project Sahaay Q3 Milestone Summary:\n"
        "Key Finding: Deterministic UI Automation achieved 100% precision.\n"
        "Performance: Browser Native Messaging bridge latency under 15ms.\n"
        "Security: Zero false success invariant verified across all test runs."
    )
    report_file.write_text(report_content, encoding="utf-8")

    # 1. Ingest authorized document via CapabilityExecutor
    ingest_result = await env["executor"].execute(
        "document_ingest_chunk",
        {"filePath": str(report_file)},
    )
    assert ingest_result["sourceId"] is not None
    assert ingest_result["chunksCount"] >= 1
    source_id = ingest_result["sourceId"]

    # 2. Retrieve findings deterministically
    retrieval_result = await env["executor"].execute(
        "deterministic_retrieval",
        {"query": "Key Finding"},
    )
    assert len(retrieval_result["facts"]) >= 1
    matched_fact = retrieval_result["facts"][0]
    assert "100% precision" in matched_fact["content"]
    assert matched_fact["sourceId"] == source_id

    # 3. Verify evidence persisted to SQLite ledger
    task_id = uuid4()
    action = ActionContract(
        actionId=uuid4(),
        actionType=ActionTypeEnum.READ_FILE,
        target=str(report_file),
        parameters={"query": "Key Finding"},
        expectedPostcondition="Extracted finding cited from source file",
    )
    exec_res = ExecutionResult(
        executionId=uuid4(),
        actionId=action.actionId,
        isSuccess=True,
        durationMs=20.0,
        outputData=retrieval_result,
    )
    verification = IndependentVerifier.verify_action_outcome(
        action=action,
        execution_result=exec_res,
        observed_postcondition_data={"state": "Extracted finding cited from source file"},
    )
    assert verification.status == VerificationStatusEnum.VERIFIED

    evidence = env["ledger"].record_evidence(
        task_id=task_id,
        step_id=uuid4(),
        action_id=action.actionId,
        verification_result=verification,
        narrative=f"Cited findings from {report_file.name} with SHA-256 fingerprint",
    )
    assert evidence.evidenceId is not None

    stored_evidence = env["ledger"].get_evidence_for_task(task_id)
    assert len(stored_evidence) == 1
    assert stored_evidence[0].evidenceId == evidence.evidenceId


# ===========================================================================
# WORKFLOW B: Browser Retrieval and Action with Readback
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_b_browser_retrieval_and_action(e2e_environment):
    """Workflow B: Observe browser tab, extract deadline, write to Notepad, verify readback."""
    env = e2e_environment

    # 1. Simulate active browser tab observation
    tab_data = {
        "url": "https://gov.in/schemes/application",
        "title": "Application Portal 2026",
        "pageText": "Application Deadline: 2026-11-30. Required fee: 500 INR.",
        "scrollPosition": {"x": 0, "y": 0},
        "documentDimensions": {"width": 1920, "height": 1080},
    }
    obs_res = await env["executor"].execute("browser_tab_observe", tab_data)
    assert obs_res["url"] == "https://gov.in/schemes/application"
    assert "2026-11-30" in obs_res["pageText"]

    # 2. Extract facts and propose writing to desktop destination
    dest_text = f"Deadline: 2026-11-30 (Source: {obs_res['url']})"
    set_text_res = await env["executor"].execute(
        "windows_set_control_text",
        {"hwnd": 0, "text": dest_text, "targetId": "Edit"},
    )
    assert set_text_res["success"] is True

    # 3. Independent readback verification
    verify_res = await env["executor"].execute(
        "verify_readback",
        {
            "target": "windows",
            "hwnd": 0,
            "targetId": "Edit",
            "expectedText": "Deadline: 2026-11-30",
        },
    )
    assert verify_res["isVerified"] is True
    assert "2026-11-30" in verify_res["readbackData"]["text"]


# ===========================================================================
# WORKFLOW C: Compound Task (Dependency DAG with Fact Propagation)
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_c_compound_dag_fact_propagation(e2e_environment):
    """Workflow C: DAG executes in dependency order, propagates preceding outputs, and stops on failure."""
    env = e2e_environment
    bill_file = env["tmp_path"] / "electricity_bill.txt"
    bill_file.write_text(
        "BESCOM Bill Account: 987654321 Amount: 1450.50 DueDate: 2026-11-15", encoding="utf-8"
    )

    task = TaskContract(
        taskId=uuid4(),
        sessionId=env["session"].sessionId,
        goal="Extract electricity bill details and summarize in Notepad",
        taskType="combined_retrieval_and_action",
    )
    durable_storage.save_task(task)

    nodes = [
        TaskDAGNode(
            step_id="step-1",
            capability_id="document_ingest_chunk",
            action_type="custom",
            instruction="Ingest electricity bill file",
            parameters={"filePath": str(bill_file)},
        ),
        TaskDAGNode(
            step_id="step-2",
            capability_id="windows_launch_app",
            action_type="custom",
            instruction="Launch Notepad editor",
            dependencies=["step-1"],
            parameters={"application": "notepad.exe"},
        ),
        TaskDAGNode(
            step_id="step-3",
            capability_id="windows_set_control_text",
            action_type="set_control_text",
            instruction="Write summary to Notepad",
            dependencies=["step-2"],
            parameters={
                "hwnd": 0,
                "targetId": "Edit",
                "text": "Electricity Bill Summary: BESCOM Amount 1450.50 Due 2026-11-15",
            },
        ),
    ]

    report = await env["dag_engine"].execute_dag(
        task=task,
        nodes=nodes,
        active_grants=[env["grant"]],
    )

    assert report.is_success is True
    assert report.completed_steps_count == 3
    assert len(report.evidence_ids) == 3

    # Check evidence persisted for each step
    evidence_list = env["ledger"].get_evidence_for_task(task.taskId)
    assert len(evidence_list) == 3


@pytest.mark.asyncio
async def test_workflow_c_failure_stops_unsafe_downstream_steps(e2e_environment):
    """Workflow C Safety: Failed prerequisite strictly halts downstream execution."""
    env = e2e_environment
    task = TaskContract(
        taskId=uuid4(),
        sessionId=env["session"].sessionId,
        goal="Process non-existent file and perform downstream actions",
        taskType="combined_retrieval_and_action",
    )
    durable_storage.save_task(task)

    nodes = [
        TaskDAGNode(
            step_id="step-1",
            capability_id="document_ingest_chunk",
            action_type="custom",
            instruction="Ingest non-existent file",
            parameters={"filePath": "C:/non_existent/path/missing_file.pdf"},
        ),
        TaskDAGNode(
            step_id="step-2",
            capability_id="windows_set_control_text",
            action_type="set_control_text",
            instruction="Should never execute due to failed dependency",
            dependencies=["step-1"],
            parameters={"hwnd": 0, "text": "Unsafe write"},
        ),
    ]

    report = await env["dag_engine"].execute_dag(
        task=task,
        nodes=nodes,
        active_grants=[env["grant"]],
    )

    assert report.is_success is False
    assert report.final_status == TaskStatusEnum.FAILED
    assert report.completed_steps_count == 0
    assert "step-1" in (report.error or "")
    assert "step-2" not in report.step_results


# ===========================================================================
# WORKFLOW D: Windows Operations (Launch Allowlist, Control & System Volume)
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_d_windows_operations_and_allowlist(e2e_environment):
    """Workflow D: Permitted app launch, UI Automation interaction, system volume control."""
    env = e2e_environment

    # 1. Permitted app launch (Notepad)
    launch_res = await env["executor"].execute(
        "windows_launch_app",
        {"application": "notepad.exe"},
    )
    assert launch_res["success"] is True

    # 2. Blocked app launch (Command prompt / PowerShell blocked by security policy)
    action_contract = ActionContract(
        actionId=uuid4(),
        actionType=ActionTypeEnum.CLICK_DESKTOP_CONTROL,
        target="cmd.exe",
        parameters={"command": "dir"},
        expectedPostcondition="ran",
    )
    decision = ActionGate.evaluate(
        action=action_contract,
        active_grants=[env["grant"]],
    )
    assert decision.decision == PolicyDecisionEnum.DENY
    assert "forbidden execution subsystem" in decision.reason.lower()

    # 3. System volume control and readback
    vol_set = await env["executor"].execute(
        "windows_set_volume",
        {"volumePercent": 65},
    )
    assert vol_set["success"] is True
    assert vol_set["volumePercent"] == 65

    vol_get = await env["executor"].execute("windows_get_volume", {})
    assert vol_get["volumePercent"] == 65


# ===========================================================================
# WORKFLOW E: Retrieval-Only Non-Mutation Invariant
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_e_retrieval_only_blocks_state_modification(e2e_environment):
    """Workflow E: Retrieval-only task strictly blocks state-modifying actions via Action Gate."""
    env = e2e_environment
    task = TaskContract(
        taskId=uuid4(),
        sessionId=env["session"].sessionId,
        goal="Summarize electricity bill (Ask / Retrieval-only mode)",
        taskType="retrieval_only",
    )
    durable_storage.save_task(task)

    # State-changing action proposed under retrieval-only task
    state_changing_node = TaskDAGNode(
        step_id="step-write",
        capability_id="windows_set_control_text",
        action_type="set_control_text",
        instruction="Attempt to write text during retrieval-only task",
        parameters={"hwnd": 0, "text": "Unauthorized modification"},
    )

    report = await env["dag_engine"].execute_dag(
        task=task,
        nodes=[state_changing_node],
        active_grants=[env["grant"]],
    )

    # Must be halted/denied by Action Gate without mutating desktop
    assert report.is_success is False
    assert report.final_status == TaskStatusEnum.HANDOFF_REQUESTED
    assert "requires user authorization" in (report.error or "")
