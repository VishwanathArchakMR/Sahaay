"""Milestone 11: Intelligent Task Completion Engine Verification.

Validates the complete execution loop across all 7 acceptance workflows:
- Workflow A: Local Research (Ingest latest project report, extract key findings, cite source, persist evidence, handle missing file).
- Workflow B: Browser to Desktop (Observe active tab notice, extract deadline + URL, launch Notepad, write summary, verify readback).
- Workflow C: Compound File and Desktop Workflow (Ingest bill, extract amount + due date, write to Notepad, verify readback).
- Workflow D: Internet Research and Comparison (Web search + local notes retrieval, date comparison, non-mutation invariant).
- Workflow E: Windows Application Action (Launch Calculator, inspect window, enter calculation, verify readback).
- Workflow F: Voice-to-Task Pipeline (Microphone audio chunk transcription -> structured plan -> DAG execution -> Task Passport).
- Workflow G: Failure & Recovery (Prerequisite failure halts downstream steps, offline simulation prevented, Action Gate enforcement).
"""

import io
import wave
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sahaay_core.api.v1.sessions import active_sessions
from sahaay_core.api.v1.workflows import active_grants
from sahaay_core.context.store import ContextStore
from sahaay_core.contracts.models import (
    ConsentGrant,
    Session,
    TaskContract,
    TaskStatusEnum,
)
from sahaay_core.main import app
from sahaay_core.models.meta.muse_voice import MuseVoiceClient
from sahaay_core.orchestration.dag_engine import TaskDagEngine, TaskDAGNode
from sahaay_core.sources.document_ingestion import DocumentIngestionError, DocumentIngestionService
from sahaay_core.sources.manager import SourceManager
from sahaay_core.storage.persistence import durable_storage

client = TestClient(app)


@pytest.fixture
def m11_session():
    """Create a persistent test session and consent grant for Milestone 11."""
    session_id = uuid4()
    session = Session(sessionId=session_id, localOnlyMode=False)
    active_sessions[session_id] = session
    durable_storage.save_session(session)

    grant = ConsentGrant(
        grantId=uuid4(),
        sessionId=session_id,
        scope="*",
        purpose="Milestone 11 Intelligent Task Engine Verification",
    )
    active_grants[session_id] = [grant]
    durable_storage.save_consent_grant(grant)

    return {"session": session, "grant": grant}


# ===========================================================================
# WORKFLOW A: Local Research
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_a_local_report_research(m11_session):
    """Workflow A: Find latest report, extract important findings, cite source, persist evidence."""
    sess = m11_session["session"]
    report_file = Path("c:/Sahaay/data/fixtures/project_report.txt")
    assert report_file.exists(), "Project report fixture must exist"

    res = client.post(
        "/api/v1/workflows/execute-goal",
        json={
            "sessionId": str(sess.sessionId),
            "goal": "Find my latest project report and summarize the important findings",
            "workflowMode": "understand_and_act",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["isVerified"] is True
    assert data["completedSteps"] == 3
    assert len(data["evidenceIds"]) >= 1

    # Verify findings are extracted from the actual report
    facts = data["accumulatedFacts"]
    assert "project_report" in str(facts) or "findings" in str(facts) or "Key Finding" in str(facts)

    # Negative test: missing document produces truthful failure
    doc_ingestion = DocumentIngestionService(SourceManager(), ContextStore())
    with pytest.raises(DocumentIngestionError) as exc_info:
        doc_ingestion.ingest_file("c:/Sahaay/data/fixtures/non_existent_report_999.txt")
    assert "File not found or inaccessible" in str(exc_info.value)


# ===========================================================================
# WORKFLOW B: Browser to Desktop
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_b_browser_to_desktop_transfer(m11_session):
    """Workflow B: Observe active webpage, extract deadline + URL, launch Notepad, write, verify readback."""
    sess = m11_session["session"]

    res = client.post(
        "/api/v1/workflows/execute-goal",
        json={
            "sessionId": str(sess.sessionId),
            "goal": "Find the deadline on my active test webpage and write it to Notepad with the source URL",
            "workflowMode": "understand_and_act",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["isVerified"] is True
    assert data["completedSteps"] == 4

    # Verify structured plan steps
    step_results = data["stepResults"]
    assert "step-b2d-1" in step_results
    assert "step-b2d-3" in step_results
    assert "step-b2d-4" in step_results

    # Verify readback confirmed deadline
    readback_step = step_results["step-b2d-4"]["data"]
    assert readback_step["isVerified"] is True

    # Verify Task Passport updated
    passport = data["passport"]
    assert passport["verification_status"] == "VERIFIED"
    assert len(passport["milestones"]) >= 4


# ===========================================================================
# WORKFLOW C: Compound File and Desktop Workflow
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_c_bill_extraction_and_notepad(m11_session):
    """Workflow C: Ingest electricity bill, extract amount + due date, write to Notepad, verify readback."""
    sess = m11_session["session"]

    res = client.post(
        "/api/v1/workflows/execute-goal",
        json={
            "sessionId": str(sess.sessionId),
            "goal": "Find my electricity bill, extract the amount and due date, and prepare a summary in Notepad",
            "workflowMode": "understand_and_act",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["isVerified"] is True
    assert data["completedSteps"] == 5

    # Verify DAG propagated extracted bill facts
    facts = data["accumulatedFacts"]
    assert "due_date" in facts or "amount_due" in facts or "bill_summary" in facts


# ===========================================================================
# WORKFLOW D: Internet Research and Comparison
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_d_research_and_comparison(m11_session):
    """Workflow D: Web search + local notes retrieval, date comparison, non-mutation invariant."""
    sess = m11_session["session"]

    res = client.post(
        "/api/v1/workflows/execute-goal",
        json={
            "sessionId": str(sess.sessionId),
            "goal": "Research the current application deadline, compare it with the date in my local notes, and explain whether they conflict",
            "workflowMode": "ask",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["isVerified"] is True

    # Invariant: No state-changing desktop mutations occurred
    for _step_id, step_data in data["stepResults"].items():
        assert "windows_set_control_text" != step_data.get("capabilityId")


# ===========================================================================
# WORKFLOW E: Windows Application Action (Calculator)
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_e_calculator_calculation(m11_session):
    """Workflow E: Launch Calculator, inspect window, enter calculation, verify readback."""
    sess = m11_session["session"]

    res = client.post(
        "/api/v1/workflows/execute-goal",
        json={
            "sessionId": str(sess.sessionId),
            "goal": "Open Calculator and calculate 125 multiplied by 24",
            "workflowMode": "do",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["isVerified"] is True
    assert data["completedSteps"] == 4

    # Verify calculation readback value 3000
    verify_data = data["stepResults"]["step-calc-4"]["data"]
    assert verify_data["isVerified"] is True
    assert "3000" in str(verify_data.get("readbackData", {}).get("text", ""))


# ===========================================================================
# WORKFLOW F: Voice-to-Task Pipeline
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_f_voice_to_task_pipeline(m11_session):
    """Workflow F: Microphone audio transcription pipeline directly feeds into task execution."""
    sess = m11_session["session"]

    # 1. Generate real synthetic 16-bit PCM WAV audio buffer
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 0.5s tone audio
        wf.writeframes(b"\x00\x7f" * 8000)
    audio_bytes = buf.getvalue()

    # 2. Transcribe via Muse Voice Transcribe pipeline
    voice_client = MuseVoiceClient()
    trans_res = await voice_client.transcribe_audio_chunk(
        audio_bytes=audio_bytes,
        content_type="audio/wav",
        language_hints=["en"],
    )
    assert trans_res.transcript is not None
    assert len(trans_res.transcript) > 0

    # 3. Feed transcript directly into execute-goal
    res = client.post(
        "/api/v1/workflows/execute-goal",
        json={
            "sessionId": str(sess.sessionId),
            "goal": trans_res.transcript,
            "workflowMode": "understand_and_act",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("COMPLETED", "VERIFIED")
    assert len(data["evidenceIds"]) >= 1


# ===========================================================================
# WORKFLOW G: Failure, Safety, and Recovery
# ===========================================================================
@pytest.mark.asyncio
async def test_workflow_g_failure_halts_downstream_and_prevents_false_success(m11_session):
    """Workflow G: Prerequisite failure halts downstream steps; simulation never yields verified."""
    sess = m11_session["session"]

    task = TaskContract(
        taskId=uuid4(),
        sessionId=sess.sessionId,
        goal="Execute compound workflow with deliberately missing prerequisite",
        taskType="combined_retrieval_and_action",
    )
    durable_storage.save_task(task)

    nodes = [
        TaskDAGNode(
            step_id="step-fail-1",
            capability_id="document_ingest_chunk",
            action_type="read_file",
            instruction="Ingest missing file",
            parameters={"filePath": "c:/missing_path/does_not_exist.txt"},
        ),
        TaskDAGNode(
            step_id="step-fail-2",
            capability_id="windows_set_control_text",
            action_type="set_control_text",
            instruction="Dangerous downstream step that must NOT execute",
            dependencies=["step-fail-1"],
            parameters={"hwnd": 0, "targetId": "Edit", "text": "Should not be written"},
        ),
    ]

    engine = TaskDagEngine()
    report = await engine.execute_dag(task=task, nodes=nodes, active_grants=[m11_session["grant"]])

    # Prerequisite failed -> downstream step halted
    assert report.is_success is False
    assert report.final_status == TaskStatusEnum.FAILED
    assert report.completed_steps_count == 0
    assert "step-fail-1" in report.step_results
    assert report.step_results["step-fail-1"]["success"] is False
    assert (
        "step-fail-2" not in report.step_results
        or report.step_results["step-fail-2"]["success"] is False
    )

    # Stored task reflects failure
    stored_task = durable_storage.get_task(task.taskId)
    assert stored_task is not None
    assert stored_task.status == TaskStatusEnum.FAILED
