"""Tests for Task Orchestration State Machine."""

from uuid import uuid4

import pytest
from sahaay_core.contracts.models import (
    ActionContract,
    ActionTypeEnum,
    PolicyDecisionEnum,
    TaskStatusEnum,
)
from sahaay_core.orchestration.orchestrator import (
    InvalidStateTransitionError,
    TaskOrchestrator,
)


def test_valid_task_state_transitions():
    orchestrator = TaskOrchestrator()
    session_id = uuid4()
    task = orchestrator.create_task(
        session_id=session_id, goal="Extract report summary"
    )
    assert task.status == TaskStatusEnum.CREATED

    # Transitions follow: CREATED -> PLANNING -> OBSERVING -> PROPOSING -> AUTHORIZING -> EXECUTING -> VERIFYING -> COMPLETED
    task = orchestrator.transition_state(task.taskId, TaskStatusEnum.PLANNING)
    assert task.status == TaskStatusEnum.PLANNING

    task = orchestrator.transition_state(task.taskId, TaskStatusEnum.OBSERVING)
    assert task.status == TaskStatusEnum.OBSERVING

    task = orchestrator.transition_state(task.taskId, TaskStatusEnum.PROPOSING)
    assert task.status == TaskStatusEnum.PROPOSING

    task = orchestrator.transition_state(task.taskId, TaskStatusEnum.AUTHORIZING)
    assert task.status == TaskStatusEnum.AUTHORIZING

    task = orchestrator.transition_state(task.taskId, TaskStatusEnum.EXECUTING)
    assert task.status == TaskStatusEnum.EXECUTING

    task = orchestrator.transition_state(task.taskId, TaskStatusEnum.VERIFYING)
    assert task.status == TaskStatusEnum.VERIFYING

    task = orchestrator.transition_state(task.taskId, TaskStatusEnum.COMPLETED)
    assert task.status == TaskStatusEnum.COMPLETED
    assert task.completedAt is not None


def test_invalid_task_state_transitions_rejected():
    orchestrator = TaskOrchestrator()
    session_id = uuid4()
    task = orchestrator.create_task(session_id=session_id, goal="Quick jump test")

    # Skipping directly from CREATED to EXECUTING must raise error
    with pytest.raises(InvalidStateTransitionError):
        orchestrator.transition_state(task.taskId, TaskStatusEnum.EXECUTING)

    # Transitioning from COMPLETED to OBSERVING must raise error
    orchestrator.transition_state(task.taskId, TaskStatusEnum.PLANNING)
    orchestrator.transition_state(task.taskId, TaskStatusEnum.OBSERVING)
    orchestrator.transition_state(task.taskId, TaskStatusEnum.PROPOSING)
    orchestrator.transition_state(task.taskId, TaskStatusEnum.AUTHORIZING)
    orchestrator.transition_state(task.taskId, TaskStatusEnum.EXECUTING)
    orchestrator.transition_state(task.taskId, TaskStatusEnum.VERIFYING)
    orchestrator.transition_state(task.taskId, TaskStatusEnum.COMPLETED)

    with pytest.raises(InvalidStateTransitionError):
        orchestrator.transition_state(task.taskId, TaskStatusEnum.OBSERVING)


def test_cancellation_blocks_future_action_dispatch():
    orchestrator = TaskOrchestrator()
    session_id = uuid4()
    task = orchestrator.create_task(session_id=session_id, goal="Cancellable task")

    orchestrator.transition_state(task.taskId, TaskStatusEnum.PLANNING)
    orchestrator.cancel_task(task.taskId)
    assert task.status == TaskStatusEnum.CANCELLED

    # Attempting to propose an action when cancelled must result in DENY
    action = ActionContract(
        actionType=ActionTypeEnum.READ_FILE,
        target="C:\\data\\test.txt",
        expectedPostcondition="read",
    )
    decision = orchestrator.propose_action(
        task_id=task.taskId,
        step_id=uuid4(),
        action=action,
        active_grants=[],
    )
    assert decision.decision == PolicyDecisionEnum.DENY
    assert "cancelled" in decision.reason.lower()
