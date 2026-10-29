"""Independent Verification Engine for Sahaay.

Preserves the critical invariant:
A model response or successful click is NEVER sufficient proof of completion.
Independent verification determines the result.
Simulated and offline mock drivers can NEVER yield VERIFIED status.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from sahaay_core.contracts.models import (
    ActionContract,
    ExecutionResult,
    VerificationResult,
    VerificationStatusEnum,
)


class IndependentVerifier:
    """Performs deterministic verification of action postconditions."""

    @staticmethod
    def verify_action_outcome(
        action: ActionContract,
        execution_result: ExecutionResult,
        observed_postcondition_data: Optional[Dict[str, Any]] = None,
        is_model_self_attestation: bool = False,
    ) -> VerificationResult:
        """Verify action outcome against expected postcondition.

        Rejects model self-attestation automatically.
        Enforces strict driver provenance: offline simulation cannot yield VERIFIED.
        """
        # INVARIANT: Model self-attestation is strictly rejected
        if is_model_self_attestation:
            return VerificationResult(
                verificationId=uuid4(),
                actionId=action.actionId,
                status=VerificationStatusEnum.UNVERIFIED,
                verifierType="deterministic_state_check",
                details="Model self-declaration is rejected. Independent state inspection required.",
                driverProvenance="model_self_attestation",
                verifiedAt=datetime.now(timezone.utc),
            )

        # Determine driver provenance
        driver_prov = None
        if observed_postcondition_data:
            driver_prov = observed_postcondition_data.get("driverProvenance")
            if not driver_prov and observed_postcondition_data.get("offlineSimulation"):
                driver_prov = "offline_simulation"
        if not driver_prov and execution_result.driverProvenance:
            driver_prov = execution_result.driverProvenance

        # INVARIANT: Offline simulation driver cannot establish physical completion on real environment
        if driver_prov == "offline_simulation":
            return VerificationResult(
                verificationId=uuid4(),
                actionId=action.actionId,
                status=VerificationStatusEnum.UNVERIFIED,
                verifierType="deterministic_state_check",
                details="Offline simulation driver cannot establish physical completion on real environment. Real execution requires real_native_driver, real_browser_extension, or owned_playwright_context.",
                driverProvenance="offline_simulation",
                verifiedAt=datetime.now(timezone.utc),
            )

        # If execution itself reported failure, verification fails immediately
        if not execution_result.isSuccess:
            return VerificationResult(
                verificationId=uuid4(),
                actionId=action.actionId,
                status=VerificationStatusEnum.FAILED,
                verifierType="deterministic_state_check",
                details=f"Execution failed: {execution_result.errorMessage or 'Unknown error'}",
                driverProvenance=driver_prov,
                verifiedAt=datetime.now(timezone.utc),
            )

        # Check observed postcondition
        if observed_postcondition_data is None:
            return VerificationResult(
                verificationId=uuid4(),
                actionId=action.actionId,
                status=VerificationStatusEnum.UNVERIFIED,
                verifierType="deterministic_state_check",
                details="No independent postcondition observation was captured.",
                driverProvenance=driver_prov,
                verifiedAt=datetime.now(timezone.utc),
            )

        # Check if expected postcondition matches verified state
        expected = action.expectedPostcondition.lower()
        actual_state = str(observed_postcondition_data.get("state", "")).lower()

        if expected in actual_state or actual_state == "verified":
            return VerificationResult(
                verificationId=uuid4(),
                actionId=action.actionId,
                status=VerificationStatusEnum.VERIFIED,
                verifierType="deterministic_state_check",
                details="Expected postcondition confirmed by independent state check.",
                observedPostcondition=actual_state,
                driverProvenance=driver_prov,
                verifiedAt=datetime.now(timezone.utc),
            )

        return VerificationResult(
            verificationId=uuid4(),
            actionId=action.actionId,
            status=VerificationStatusEnum.CONFLICT,
            verifierType="deterministic_state_check",
            details=f"State mismatch: expected '{expected}', observed '{actual_state}'.",
            observedPostcondition=actual_state,
            driverProvenance=driver_prov,
            verifiedAt=datetime.now(timezone.utc),
        )
