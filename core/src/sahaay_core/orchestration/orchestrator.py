"""Task Orchestration Engine and State Machine.

Owns task transitions, enforces the execution sequence:
OBSERVE -> PROPOSE -> AUTHORIZE -> EXECUTE -> VERIFY -> RECORD.
Strictly rejects invalid transitions and blocks actions when cancelled.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sahaay_core.contracts.models import (
    ActionContract,
    ConsentGrant,
    PolicyDecision,
    TaskContract,
    TaskStatusEnum,
)
from sahaay_core.policy.action_gate import ActionGate
from sahaay_core.storage.persistence import durable_storage

# Allowed state transitions for task lifecycle
VALID_TRANSITIONS: Dict[TaskStatusEnum, set[TaskStatusEnum]] = {
    TaskStatusEnum.CREATED: {TaskStatusEnum.PLANNING, TaskStatusEnum.CANCELLED},
    TaskStatusEnum.PLANNING: {
        TaskStatusEnum.OBSERVING,
        TaskStatusEnum.CANCELLED,
        TaskStatusEnum.FAILED,
    },
    TaskStatusEnum.OBSERVING: {
        TaskStatusEnum.PROPOSING,
        TaskStatusEnum.PAUSED,
        TaskStatusEnum.CANCELLED,
        TaskStatusEnum.FAILED,
        TaskStatusEnum.COMPLETED,
        TaskStatusEnum.HANDOFF_REQUESTED,
    },
    TaskStatusEnum.PROPOSING: {
        TaskStatusEnum.AUTHORIZING,
        TaskStatusEnum.PAUSED,
        TaskStatusEnum.CANCELLED,
        TaskStatusEnum.FAILED,
    },
    TaskStatusEnum.AUTHORIZING: {
        TaskStatusEnum.EXECUTING,
        TaskStatusEnum.HANDOFF_REQUESTED,
        TaskStatusEnum.PAUSED,
        TaskStatusEnum.CANCELLED,
        TaskStatusEnum.FAILED,
    },
    TaskStatusEnum.EXECUTING: {
        TaskStatusEnum.VERIFYING,
        TaskStatusEnum.FAILED,
        TaskStatusEnum.CANCELLED,
    },
    TaskStatusEnum.VERIFYING: {
        TaskStatusEnum.OBSERVING,  # Next loop/step in task
        TaskStatusEnum.COMPLETED,
        TaskStatusEnum.FAILED,
        TaskStatusEnum.CANCELLED,
    },
    TaskStatusEnum.PAUSED: {TaskStatusEnum.OBSERVING, TaskStatusEnum.CANCELLED},
    TaskStatusEnum.HANDOFF_REQUESTED: {
        TaskStatusEnum.CANCELLED,
        TaskStatusEnum.COMPLETED,
        TaskStatusEnum.OBSERVING,
    },
    TaskStatusEnum.COMPLETED: set(),
    TaskStatusEnum.FAILED: set(),
    TaskStatusEnum.CANCELLED: set(),
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal task state transition is attempted."""

    pass


class TaskOrchestrator:
    """Orchestrates task execution and enforces deterministic state transitions backed by SQLite."""

    def __init__(self) -> None:
        self._tasks: Dict[UUID, TaskContract] = {}

    def create_task(
        self, session_id: UUID, goal: str, task_type: str = "combined_retrieval_and_action"
    ) -> TaskContract:
        """Create and register a new task in CREATED status and persist it."""
        task = TaskContract(
            taskId=uuid4(),
            sessionId=session_id,
            goal=goal,
            taskType=task_type,
            status=TaskStatusEnum.CREATED,
            createdAt=datetime.now(timezone.utc),
            steps=[],
        )
        durable_storage.save_task(task)
        self._tasks[task.taskId] = task
        return task

    def get_task(self, task_id: UUID) -> Optional[TaskContract]:
        """Fetch a task by ID from cache or durable persistence."""
        task = self._tasks.get(task_id)
        if not task:
            task = durable_storage.get_task(task_id)
            if task:
                self._tasks[task_id] = task
        return task

    def transition_state(self, task_id: UUID, target_status: TaskStatusEnum) -> TaskContract:
        """Attempt to transition task status to target status and persist update."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")

        current_status = task.status
        allowed_targets = VALID_TRANSITIONS.get(current_status, set())

        if target_status not in allowed_targets:
            raise InvalidStateTransitionError(
                f"Illegal state transition from {current_status.value} to {target_status.value}."
            )

        task.status = target_status
        if target_status in (
            TaskStatusEnum.COMPLETED,
            TaskStatusEnum.FAILED,
            TaskStatusEnum.CANCELLED,
        ):
            task.completedAt = datetime.now(timezone.utc)

        durable_storage.save_task(task)
        return task

    def cancel_task(self, task_id: UUID) -> TaskContract:
        """Cancel a running task immediately and persist state."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")

        if task.status in (TaskStatusEnum.COMPLETED, TaskStatusEnum.FAILED):
            raise InvalidStateTransitionError(f"Cannot cancel a {task.status.value} task.")

        task.status = TaskStatusEnum.CANCELLED
        task.completedAt = datetime.now(timezone.utc)
        durable_storage.save_task(task)
        return task

    def pause_task(self, task_id: UUID) -> TaskContract:
        """Pause task execution."""
        return self.transition_state(task_id, TaskStatusEnum.PAUSED)

    def resume_task(self, task_id: UUID) -> TaskContract:
        """Resume task from paused state back to observing."""
        return self.transition_state(task_id, TaskStatusEnum.OBSERVING)

    def request_handoff(self, task_id: UUID) -> TaskContract:
        """Request human intervention/handoff."""
        return self.transition_state(task_id, TaskStatusEnum.HANDOFF_REQUESTED)

    def propose_action(
        self,
        task_id: UUID,
        step_id: UUID,
        action: ActionContract,
        active_grants: List[ConsentGrant],
    ) -> PolicyDecision:
        """Propose an action and evaluate through Action Gate.

        Fails immediately if task is cancelled.
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")

        is_cancelled = task.status == TaskStatusEnum.CANCELLED
        decision = ActionGate.evaluate(
            action=action,
            active_grants=active_grants,
            is_task_cancelled=is_cancelled,
            task_type=task.taskType,
        )
        return decision
