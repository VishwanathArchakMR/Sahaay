"""Action Gate Policy Engine.

Enforces deterministic authorization for all proposed computer and browser actions.
Models propose; Action Gate authorizes.
"""

from typing import List, Optional
from uuid import uuid4

from sahaay_core.contracts.models import (
    ActionContract,
    ActionTypeEnum,
    ConsentGrant,
    PolicyDecision,
    PolicyDecisionEnum,
)

# Strict allowlist of operations permissible in Sahaay
PERMITTED_ACTIONS = {
    ActionTypeEnum.READ_FILE,
    ActionTypeEnum.SEARCH_FILES,
    ActionTypeEnum.GET_ACTIVE_TAB_INFO,
    ActionTypeEnum.GET_TAB_CONTENT,
    ActionTypeEnum.NAVIGATE_BROWSER_TAB,
    ActionTypeEnum.CLICK_BROWSER_ELEMENT,
    ActionTypeEnum.INPUT_BROWSER_TEXT,
    ActionTypeEnum.FOCUS_WINDOW,
    ActionTypeEnum.GET_ACTIVE_WINDOW,
    ActionTypeEnum.LIST_OPEN_WINDOWS,
    ActionTypeEnum.CLICK_DESKTOP_CONTROL,
    ActionTypeEnum.TYPE_DESKTOP_TEXT,
    ActionTypeEnum.SET_CONTROL_TEXT,
    ActionTypeEnum.GET_CONTROL_TEXT,
    ActionTypeEnum.SCROLL_BROWSER_TAB,
    ActionTypeEnum.FILL_FORM_FIELDS,
    ActionTypeEnum.GET_FIELD_VALUES,
}

# Operations that are strictly read-only and require lower scope threshold
READ_ONLY_ACTIONS = {
    ActionTypeEnum.READ_FILE,
    ActionTypeEnum.SEARCH_FILES,
    ActionTypeEnum.GET_ACTIVE_TAB_INFO,
    ActionTypeEnum.GET_TAB_CONTENT,
    ActionTypeEnum.GET_ACTIVE_WINDOW,
    ActionTypeEnum.LIST_OPEN_WINDOWS,
    ActionTypeEnum.SCROLL_BROWSER_TAB,
    ActionTypeEnum.GET_CONTROL_TEXT,
    ActionTypeEnum.GET_FIELD_VALUES,
}


class ActionGate:
    """Deterministic authorization gate for proposed actions."""

    @staticmethod
    def evaluate(
        action: ActionContract,
        active_grants: List[ConsentGrant],
        is_task_cancelled: bool = False,
        task_type: Optional[str] = None,
    ) -> PolicyDecision:
        """Evaluate an action against deterministic policies and active consent grants."""
        # 1. If task is cancelled, immediately deny all future actions
        if is_task_cancelled:
            return PolicyDecision(
                decisionId=uuid4(),
                actionId=action.actionId,
                decision=PolicyDecisionEnum.DENY,
                reason="Task has been cancelled; all subsequent actions are blocked.",
            )

        # 1b. If task is declared retrieval_only, deny physical computer and browser actions
        if task_type == "retrieval_only" and action.actionType not in (
            ActionTypeEnum.READ_FILE,
            ActionTypeEnum.SEARCH_FILES,
            ActionTypeEnum.GET_ACTIVE_TAB_INFO,
            ActionTypeEnum.GET_TAB_CONTENT,
            ActionTypeEnum.GET_ACTIVE_WINDOW,
            ActionTypeEnum.LIST_OPEN_WINDOWS,
        ):
            return PolicyDecision(
                decisionId=uuid4(),
                actionId=action.actionId,
                decision=PolicyDecisionEnum.DENY,
                reason="Task is declared retrieval-only; physical computer and browser actions are blocked.",
            )

        # 2. Strict allowlist check
        if action.actionType not in PERMITTED_ACTIONS:
            return PolicyDecision(
                decisionId=uuid4(),
                actionId=action.actionId,
                decision=PolicyDecisionEnum.DENY,
                reason=f"Action type '{action.actionType}' is not in the permitted operation allowlist.",
            )

        # 3. Target validation - no arbitrary system shells or root drives
        forbidden_targets = ["powershell", "cmd.exe", "bash", "sh", "regedit", "format"]
        target_lower = action.target.lower()
        for forbidden in forbidden_targets:
            if forbidden in target_lower:
                return PolicyDecision(
                    decisionId=uuid4(),
                    actionId=action.actionId,
                    decision=PolicyDecisionEnum.DENY,
                    reason=f"Target '{action.target}' contains forbidden execution subsystem.",
                )

        # 4. Consent and scope verification
        required_scope = f"{action.actionType.value}:{action.target}"
        has_matching_grant = any(
            (
                not grant.isRevoked
                and (
                    grant.scope == "*"
                    or grant.scope == action.actionType.value
                    or grant.scope in required_scope
                )
            )
            for grant in active_grants
        )

        if not has_matching_grant:
            # If high risk and no grant, require explicit clarification/consent
            if action.estimatedRisk in ("MEDIUM", "HIGH"):
                return PolicyDecision(
                    decisionId=uuid4(),
                    actionId=action.actionId,
                    decision=PolicyDecisionEnum.CLARIFY,
                    reason=f"Missing explicit consent grant for scope: {required_scope}",
                    requiredGrantScope=required_scope,
                    clarificationPrompt=f"Authorize action '{action.actionType.value}' on target '{action.target}'?",
                )
            # For read-only actions, allow if safe, or deny if out-of-scope
            if action.actionType not in READ_ONLY_ACTIONS:
                return PolicyDecision(
                    decisionId=uuid4(),
                    actionId=action.actionId,
                    decision=PolicyDecisionEnum.DENY,
                    reason=f"Action requires authorized grant with scope '{required_scope}'.",
                    requiredGrantScope=required_scope,
                )

        return PolicyDecision(
            decisionId=uuid4(),
            actionId=action.actionId,
            decision=PolicyDecisionEnum.ALLOW,
            reason="Action conforms to permitted allowlist and active policy scope.",
        )
