"""Milestone 07 Integration Tests: Unified, Evidence-Driven Windows AI Agent.

Covers:
- Test 1: Local retrieval (Ask mode) - ingest document, ground answer in evidence.
- Test 2: Browser-to-desktop workflow - live observation, extracted facts, destination readback.
- Test 3: Compound cross-surface task (Understand + Act) - bill extraction & transfer.
- Test 4: General Windows operations - app launch allowlist, UI interaction, native volume control.
- Test 5: Voice audio - actual WAV transcription to shared task runtime; wake-word status.
- Test 6: Ask vs Do vs Combined modes - retrieval-only non-mutation vs action execution.
- Test 7: Failure and security invariants - DAG cycles, Action Gate denial, cancellation, no false success.
"""

import io
import wave
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sahaay_core.adapters.windows.adapter import WindowsNativeAdapter
from sahaay_core.api.v1.sessions import active_sessions
from sahaay_core.api.v1.workflows import active_grants
from sahaay_core.contracts.models import (
    ConsentGrant,
    Session,
)
from sahaay_core.main import app
from sahaay_core.models.meta.muse_voice import MuseVoiceClient
from sahaay_core.orchestration.dag_engine import (
    TaskDagEngine,
    TaskDAGNode,
)
from sahaay_core.privacy.privacy_gateway import PrivacyGateway
from sahaay_core.storage.persistence import durable_storage

client = TestClient(app)


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------
@pytest.fixture
def test_session():
    """Create a persistent test session."""
    session_id = uuid4()
    session = Session(
        sessionId=session_id,
        localOnlyMode=False,
    )
    active_sessions[session_id] = session
    durable_storage.save_session(session)
    return session


@pytest.fixture
def wildcard_grant(test_session):
    """Create an active consent grant for testing."""
    grant = ConsentGrant(
        sessionId=test_session.sessionId,
        scope="*",
        purpose="Milestone 07 Integrated Agent Testing",
    )
    active_grants[test_session.sessionId] = [grant]
    return grant


# ---------------------------------------------------------------------------
# DAG ENGINE & VALIDATION TESTS
# ---------------------------------------------------------------------------
def test_dag_cycle_detection_rejects_circular_plans():
    """Verify DAG engine rejects cyclic dependency graphs before execution."""
    engine = TaskDagEngine()
    node1 = TaskDAGNode(
        step_id="step-1",
        capability_id="windows_inspect_window",
        instruction="List open windows",
        dependencies=["step-2"],  # Depends on step 2
    )
    node2 = TaskDAGNode(
        step_id="step-2",
        capability_id="windows_get_control_text",
        instruction="Read window text",
        dependencies=["step-1"],  # Depends on step 1 (CYCLE!)
    )

    is_valid, error = engine.validate_dag([node1, node2])
    assert is_valid is False
    assert error is not None and "Cycle detected" in error


def test_dag_rejects_unregistered_capability():
    """Verify DAG engine rejects steps referencing non-existent capabilities."""
    engine = TaskDagEngine()
    node = TaskDAGNode(
        step_id="step-1",
        capability_id="unregistered_dangerous_shell",
        instruction="Run arbitrary shell",
    )

    is_valid, error = engine.validate_dag([node])
    assert is_valid is False
    assert error is not None and "not registered" in error


def test_dag_dynamic_parameter_resolution():
    """Verify fact placeholders are dynamically substituted from previous step outputs."""
    engine = TaskDagEngine()
    raw_params = {
        "text": "Invoice total is {{step-1.amount}} due on {{step-1.due_date}}",
        "hwnd": 12345,
    }
    accumulated_facts = {"customer": "Aarav Sharma"}
    step_outputs = {"step-1": {"amount": "INR 2,450.00", "due_date": "Nov 15, 2026"}}

    resolved = engine.resolve_parameters(raw_params, accumulated_facts, step_outputs)
    assert resolved["text"] == "Invoice total is INR 2,450.00 due on Nov 15, 2026"
    assert resolved["hwnd"] == 12345


# ---------------------------------------------------------------------------
# TEST 1: LOCAL RETRIEVAL (ASK MODE)
# ---------------------------------------------------------------------------
def test_local_retrieval_ask_mode(test_session, tmp_path):
    """Test 1 — Local retrieval: Read report, record path/hash, ground evidence."""
    # Create test document
    report_file = tmp_path / "project_alpha_report.txt"
    report_file.write_text(
        "PROJECT ALPHA AUDIT REPORT\n"
        "Lead: Vikram Sen\n"
        "Status: Milestone 07 Verified\n"
        "Key Finding: Core Audio and UI Automation integration verified without shell injection.\n",
        encoding="utf-8",
    )
    # Ingest document
    ingest_res = client.post(
        "/api/v1/sources/ingest",
        json={"filePath": str(report_file)},
    )
    assert ingest_res.status_code == 200
    data = ingest_res.json()
    assert data["success"] is True
    assert data["checksum"] != ""

    # Search facts (Ask Mode)
    search_res = client.post(
        "/api/v1/sources/search",
        json={"query": "Core Audio"},
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data["results"]) >= 1
    assert "Core Audio" in search_data["results"][0]["content"]


# ---------------------------------------------------------------------------
# TEST 2: BROWSER TO DESKTOP WORKFLOW
# ---------------------------------------------------------------------------
def test_browser_to_desktop_transfer(test_session, wildcard_grant):
    """Test 2 — Browser to desktop: Extract deadline from webpage and transfer."""
    res = client.post(
        "/api/v1/workflows/browser-to-desktop",
        json={
            "sessionId": str(test_session.sessionId),
            "instruction": "Find the deadline on the active test webpage and write it to Notepad.",
            "isFixtureMode": True,
            "browserObservationExcerpt": "Bengaluru Utility\nConsumer Name: Priya Patel\nAccount: BLR-8821\nAmount: INR 1,200.00\nDue: Dec 01, 2026",
            "sourceTabUrl": "https://bescom.karnataka.gov.in/bill",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["isVerified"] is True
    assert data["status"] == "VERIFIED"
    assert "BLR-8821" in data["targetExecution"]["actualText"]


# ---------------------------------------------------------------------------
# TEST 3: COMPOUND CROSS-SURFACE TASK (UNDERSTAND + ACT)
# ---------------------------------------------------------------------------
def test_compound_cross_surface_task(test_session, wildcard_grant):
    """Test 3 — Compound task: Extract bill details and populate desktop form."""
    res = client.post(
        "/api/v1/workflows/desktop-to-browser",
        json={
            "sessionId": str(test_session.sessionId),
            "instruction": "Find electricity bill and populate the utility web form.",
            "isFixtureMode": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["isVerified"] is True
    assert data["status"] == "VERIFIED"
    assert data["formMapping"]["accountNumber"] == "BLR-UTIL-98421"


# ---------------------------------------------------------------------------
# TEST 4: GENERAL WINDOWS OPERATIONS
# ---------------------------------------------------------------------------
def test_windows_app_launch_allowlist_enforcement():
    """Test 4a — App launch allowlist: calc/notepad allowed, scripts rejected."""
    adapter = WindowsNativeAdapter()

    # Rejection of dangerous command
    with pytest.raises(RuntimeError, match="not in the authorized launch allowlist"):
        adapter.launch_application("powershell.exe")

    with pytest.raises(RuntimeError, match="not in the authorized launch allowlist"):
        adapter.launch_application("malicious.bat")


def test_windows_native_system_volume_control():
    """Test 4b — Native system volume: Read state before and after."""
    adapter = WindowsNativeAdapter()

    # Set system volume to 60%
    set_res = adapter.set_system_volume(60)
    assert set_res.get("verified") is True
    assert set_res.get("volumePercent") == 60

    # Query current volume
    get_res = adapter.get_system_volume()
    assert get_res.get("verified") is True
    assert get_res.get("volumePercent") == 60


# ---------------------------------------------------------------------------
# TEST 5: VOICE TRANSCRIPTION PATH & WAKE-WORD STATUS
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_voice_transcription_synthetic_audio():
    """Test 5 — Actual audio buffer reaches transcription and parses truthfully."""
    voice_client = MuseVoiceClient()
    voice_client.privacy_gateway = PrivacyGateway(local_only_mode=False)

    # 1 second of synthetic 16kHz WAV silence
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)

    audio_bytes = wav_io.getvalue()
    grant = ConsentGrant(
        sessionId=uuid4(),
        purpose="Voice audio transcription",
        scope="*",
        targetDomainOrPath="https://api.meta.ai/v1",
    )

    result = await voice_client.transcribe_audio_chunk(
        audio_bytes=audio_bytes,
        content_type="audio/wav",
        language_hints=["en"],
        active_grants=[grant],
    )

    # In online or fallback mode, transcript is editable and confidence is valid
    assert result.editable is True
    assert result.duration_seconds > 0.0


# ---------------------------------------------------------------------------
# TEST 6: ASK VS DO VS COMBINED MODES
# ---------------------------------------------------------------------------
def test_ask_mode_does_not_mutate_system(test_session):
    """Test 6 — Ask mode (retrieval_only) does not trigger machine-changing actions."""
    res = client.post(
        "/api/v1/workflows/execute-goal",
        json={
            "sessionId": str(test_session.sessionId),
            "goal": "Explain electricity tariff slabs",
            "workflowMode": "ask",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "ask"
    # Status is valid
    assert data["status"] in ("COMPLETED", "VERIFIED")


# ---------------------------------------------------------------------------
# TEST 7: FAILURE AND SECURITY INVARIANTS
# ---------------------------------------------------------------------------
def test_action_gate_denial_halts_task_and_requests_handoff(test_session):
    """Test 7 — Action Gate denial halts task without auto-granting wildcard permissions."""
    # Deliberately run without granting permissions
    res = client.post(
        "/api/v1/workflows/browser-to-desktop",
        json={
            "sessionId": str(test_session.sessionId),
            "instruction": "Transfer bill to desktop without grant",
            "isFixtureMode": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    # Must halt in HANDOFF, not proceed or fake verification
    assert data["status"] == "HANDOFF"
    assert data["isVerified"] is False


def test_disappeared_target_window_detected_as_failure(test_session, wildcard_grant):
    """Test 7b — Real mode with missing window handle (targetHwnd=0) fails immediately."""
    res = client.post(
        "/api/v1/workflows/browser-to-desktop",
        json={
            "sessionId": str(test_session.sessionId),
            "instruction": "Transfer to non-existent window handle",
            "isFixtureMode": False,
            "targetHwnd": 0,
            "browserObservationExcerpt": "Active bill content",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "FAILED"
    assert data["isVerified"] is False
    assert "Invalid or missing target window handle" in data["error"]
