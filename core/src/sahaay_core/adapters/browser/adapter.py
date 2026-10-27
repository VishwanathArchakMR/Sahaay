"""Browser Integration Adapter.

Processes authorized browser observations and executes bounded tab actions.
"""

from typing import Any, Dict
from uuid import uuid4


class BrowserAdapter:
    """Adapter for browser tab inspection and permitted interactions."""

    def __init__(self) -> None:
        self.active_observations: Dict[str, Dict[str, Any]] = {}

    def ingest_tab_observation(self, observation_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and ingest real observation from browser extension."""
        url = observation_payload.get("url", "")
        title = observation_payload.get("title", "")
        obs_id = observation_payload.get("observationId", uuid4().hex)

        if not url:
            raise ValueError("Observation payload missing URL.")

        record = {
            "observationId": obs_id,
            "url": url,
            "title": title,
            "scrollPosition": observation_payload.get("scrollPosition", {"x": 0, "y": 0}),
            "documentDimensions": observation_payload.get("documentDimensions", {}),
            "visibleTextExcerpt": observation_payload.get("visibleTextExcerpt", ""),
            "accessibleElements": observation_payload.get("accessibleElements", []),
            "capturedAt": observation_payload.get("capturedAt"),
        }
        self.active_observations[obs_id] = record
        return record

    def verify_scroll_action(
        self,
        pre_scroll_y: int,
        post_scroll_y: int,
        requested_delta: int,
    ) -> Dict[str, Any]:
        """Perform independent verification on scroll action postcondition."""
        actual_delta = post_scroll_y - pre_scroll_y
        is_verified = (actual_delta != 0) and (
            (requested_delta > 0 and actual_delta > 0) or (requested_delta < 0 and actual_delta < 0)
        )

        return {
            "preScrollY": pre_scroll_y,
            "postScrollY": post_scroll_y,
            "requestedDelta": requested_delta,
            "actualDelta": actual_delta,
            "isVerified": is_verified,
            "status": "VERIFIED" if is_verified else "CONFLICT",
        }
