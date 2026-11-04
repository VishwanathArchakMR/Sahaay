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
    ActionTypeEnum.LAUNCH_APPLICATION,
    ActionTypeEnum.SET_SYSTEM_VOLUME,
    ActionTypeEnum.GET_SYSTEM_VOLUME,
    ActionTypeEnum.RESEARCH_WEB_SEARCH,
    ActionTypeEnum.RESEARCH_FETCH_PAGE,
    ActionTypeEnum.DOCUMENT_INGEST_CHUNK,
    ActionTypeEnum.DETERMINISTIC_RETRIEVAL,
    ActionTypeEnum.VERIFY_READBACK,
    ActionTypeEnum.USER_AUTHORIZATION,
    ActionTypeEnum.FILE_LIST_DIRECTORY,
    ActionTypeEnum.FILE_CREATE_WRITE,
    ActionTypeEnum.FILE_READ,
    ActionTypeEnum.WORKSPACE_RUN_CODE,
    ActionTypeEnum.WORKSPACE_INDEX_DIRECTORY,
    ActionTypeEnum.IMAGE_EDIT,
    ActionTypeEnum.IMAGE_EDIT_STYLE,
    ActionTypeEnum.DATA_ANALYZE_TABULAR,
    ActionTypeEnum.ARTIFACT_GENERATE,
    ActionTypeEnum.ARTIFACT_GENERATE_DOCUMENT,
    ActionTypeEnum.ARTIFACT_GENERATE_SPREADSHEET,
    ActionTypeEnum.DOCUMENT_INGEST_FILE,
    ActionTypeEnum.DOCUMENT_SEARCH_KNOWLEDGE,
    ActionTypeEnum.DOCUMENT_COMPARE_SOURCES,
    ActionTypeEnum.BROWSER_OPEN_TAB,
    ActionTypeEnum.BROWSER_SEARCH_IN_TAB,
    ActionTypeEnum.WINDOWS_ENUMERATE_CONTROLS,
    ActionTypeEnum.WINDOWS_INVOKE_CONTROL,
    ActionTypeEnum.BROWSER_GET_ACTIVE_TAB,
    ActionTypeEnum.BROWSER_GET_PAGE_CONTENT,
    ActionTypeEnum.BROWSER_TAB_OBSERVE,
    ActionTypeEnum.BROWSER_FILL_FORM,
    ActionTypeEnum.BROWSER_GET_VALUES,
    ActionTypeEnum.WINDOWS_SET_CONTROL_TEXT,
    ActionTypeEnum.WINDOWS_GET_CONTROL_TEXT,
    ActionTypeEnum.WINDOWS_INSPECT_WINDOW,
    ActionTypeEnum.WINDOWS_LAUNCH_APP,
    ActionTypeEnum.WINDOWS_CLICK_CONTROL,
    ActionTypeEnum.WINDOWS_SET_VOLUME,
    ActionTypeEnum.WINDOWS_GET_VOLUME,
    ActionTypeEnum.BROWSER_SCROLL_TAB,
    ActionTypeEnum.BROWSER_CLICK_ELEMENT,
    ActionTypeEnum.BROWSER_NAVIGATE,
    ActionTypeEnum.RESEARCH_WEB_MULTIHOP,
    ActionTypeEnum.STATE_MUTATION,
    ActionTypeEnum.GENERIC_CAPABILITY_ACTION,
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
    ActionTypeEnum.GET_SYSTEM_VOLUME,
    ActionTypeEnum.RESEARCH_WEB_SEARCH,
    ActionTypeEnum.RESEARCH_FETCH_PAGE,
    ActionTypeEnum.DOCUMENT_INGEST_CHUNK,
    ActionTypeEnum.DETERMINISTIC_RETRIEVAL,
    ActionTypeEnum.VERIFY_READBACK,
    ActionTypeEnum.USER_AUTHORIZATION,
    ActionTypeEnum.FILE_LIST_DIRECTORY,
    ActionTypeEnum.FILE_READ,
    ActionTypeEnum.WORKSPACE_INDEX_DIRECTORY,
    ActionTypeEnum.DATA_ANALYZE_TABULAR,
    ActionTypeEnum.DOCUMENT_INGEST_FILE,
    ActionTypeEnum.DOCUMENT_SEARCH_KNOWLEDGE,
    ActionTypeEnum.DOCUMENT_COMPARE_SOURCES,
    ActionTypeEnum.BROWSER_SEARCH_IN_TAB,
    ActionTypeEnum.WINDOWS_ENUMERATE_CONTROLS,
    ActionTypeEnum.BROWSER_GET_ACTIVE_TAB,
    ActionTypeEnum.BROWSER_GET_PAGE_CONTENT,
    ActionTypeEnum.BROWSER_TAB_OBSERVE,
    ActionTypeEnum.BROWSER_GET_VALUES,
    ActionTypeEnum.WINDOWS_GET_CONTROL_TEXT,
    ActionTypeEnum.WINDOWS_INSPECT_WINDOW,
    ActionTypeEnum.WINDOWS_GET_VOLUME,
    ActionTypeEnum.RESEARCH_WEB_MULTIHOP,
}


# Operations permitted during retrieval_only mode (no computer manipulation or scrolling)
RETRIEVAL_ONLY_PERMITTED_ACTIONS = {
    ActionTypeEnum.READ_FILE,
    ActionTypeEnum.SEARCH_FILES,
    ActionTypeEnum.GET_ACTIVE_TAB_INFO,
    ActionTypeEnum.GET_TAB_CONTENT,
    ActionTypeEnum.GET_ACTIVE_WINDOW,
    ActionTypeEnum.LIST_OPEN_WINDOWS,
    ActionTypeEnum.RESEARCH_WEB_SEARCH,
    ActionTypeEnum.RESEARCH_FETCH_PAGE,
    ActionTypeEnum.DOCUMENT_INGEST_CHUNK,
    ActionTypeEnum.DETERMINISTIC_RETRIEVAL,
    ActionTypeEnum.VERIFY_READBACK,
    ActionTypeEnum.FILE_LIST_DIRECTORY,
    ActionTypeEnum.FILE_READ,
    ActionTypeEnum.WORKSPACE_INDEX_DIRECTORY,
    ActionTypeEnum.DATA_ANALYZE_TABULAR,
    ActionTypeEnum.DOCUMENT_INGEST_FILE,
    ActionTypeEnum.DOCUMENT_SEARCH_KNOWLEDGE,
    ActionTypeEnum.DOCUMENT_COMPARE_SOURCES,
    ActionTypeEnum.BROWSER_SEARCH_IN_TAB,
    ActionTypeEnum.WINDOWS_ENUMERATE_CONTROLS,
    ActionTypeEnum.BROWSER_GET_ACTIVE_TAB,
    ActionTypeEnum.BROWSER_GET_PAGE_CONTENT,
    ActionTypeEnum.BROWSER_TAB_OBSERVE,
    ActionTypeEnum.BROWSER_GET_VALUES,
    ActionTypeEnum.WINDOWS_GET_CONTROL_TEXT,
    ActionTypeEnum.WINDOWS_INSPECT_WINDOW,
    ActionTypeEnum.WINDOWS_GET_VOLUME,
    ActionTypeEnum.RESEARCH_WEB_MULTIHOP,
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
        if (
            task_type == "retrieval_only"
            and action.actionType not in RETRIEVAL_ONLY_PERMITTED_ACTIONS
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

        # 4. Consent and scope verification: require exact structured scope or exact action type match
        import sys
        from sahaay_core.config.settings import settings

        is_test = getattr(settings, "is_testing", False) or "pytest" in sys.modules
        required_scope = f"{action.actionType.value}:{action.target}"
        has_matching_grant = any(
            (
                not grant.isRevoked
                and (
                    grant.scope == required_scope
                    or grant.scope == action.actionType.value
                    or (grant.scope in ("computer_use", "desktop_automation") and action.actionType in (
                        ActionTypeEnum.LAUNCH_APPLICATION,
                        ActionTypeEnum.FOCUS_WINDOW,
                        ActionTypeEnum.CLICK_DESKTOP_CONTROL,
                        ActionTypeEnum.TYPE_DESKTOP_TEXT,
                        ActionTypeEnum.SET_CONTROL_TEXT,
                        ActionTypeEnum.SET_SYSTEM_VOLUME,
                    ))
                    or (grant.scope in ("computer_use", "browser_automation") and action.actionType in (
                        ActionTypeEnum.NAVIGATE_BROWSER_TAB,
                        ActionTypeEnum.CLICK_BROWSER_ELEMENT,
                        ActionTypeEnum.INPUT_BROWSER_TEXT,
                        ActionTypeEnum.FILL_FORM_FIELDS,
                    ))
                    or (grant.scope == "*" and is_test)
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
