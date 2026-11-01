"""Browser Integration Adapter.

Processes authorized browser observations and executes bounded tab actions via Native Messaging Bridge.
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from sahaay_core.adapters.windows.named_pipe_client import NamedPipeClient


class BrowserAdapter:
    """Adapter for browser tab inspection and permitted interactions via Native Messaging bridge."""

    def __init__(self, pipe_name: str = "SahaayBrowserBridgePipe", allow_simulation: bool = False) -> None:
        self.pipe_name = pipe_name
        self.client = NamedPipeClient(pipe_name=pipe_name)
        self.active_observations: Dict[str, Dict[str, Any]] = {}
        self.allow_simulation = allow_simulation
        self.latest_observation_id: Optional[str] = None

    def is_connected(self) -> bool:
        """Check if Native Messaging Host is active and reachable via Named Pipe."""
        try:
            res = self.client.send_command("ping", timeout_ms=800)
            return bool(res.get("success", False))
        except Exception:
            return False

    def is_browser_attached(self) -> bool:
        """Check if a live browser extension is connected to the Native Messaging Host."""
        try:
            res = self.client.send_command("ping", timeout_ms=800)
            if res.get("success"):
                return bool(res.get("data", {}).get("isBrowserAttached", False))
            return False
        except Exception:
            return False

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
        self.latest_observation_id = obs_id
        return record

    def get_active_tab_observation(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Request real tab observation from browser extension via Native Host."""
        try:
            res = self.client.send_command(
                "get_tab_observation", session_id=session_id, timeout_ms=3000
            )
            if not res.get("success"):
                raise RuntimeError(res.get("error", "Failed to retrieve browser tab observation."))
            data = res.get("data", {})
            return self.ingest_tab_observation(data)
        except ConnectionError as ce:
            if self.allow_simulation and self.active_observations:
                return list(self.active_observations.values())[-1]
            raise ConnectionError(f"Browser bridge not reachable: {ce}") from ce

    def scroll_tab(self, delta_y: int = 300, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute bounded scroll on active browser tab and verify delta."""
        try:
            res = self.client.send_command(
                "scroll_tab",
                session_id=session_id,
                parameters={"deltaY": delta_y},
                timeout_ms=3000,
            )
            if not res.get("success"):
                raise RuntimeError(res.get("error", "Scroll action rejected by browser."))
            return res.get("data", {})
        except ConnectionError as ce:
            if not self.allow_simulation:
                raise ConnectionError("Browser bridge not connected.") from ce
            return {
                "preScrollY": 0,
                "postScrollY": delta_y,
                "requestedDeltaY": delta_y,
                "actualDeltaY": delta_y,
                "driverProvenance": "offline_simulation",
                "offlineSimulation": True,
            }

    def fill_form_fields(
        self, fields: Dict[str, Any], session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Populate input fields in the active browser tab without form submission."""
        # Validate observation binding if references are bound to snapshots
        for k in fields.keys():
            if str(k).startswith("@obs-"):
                ref_obs_id = str(k).split(":")[0][5:]
                if self.latest_observation_id and ref_obs_id != self.latest_observation_id:
                    raise ValueError(f"Stale element reference '{k}': bound to observation '{ref_obs_id}' but active observation is '{self.latest_observation_id}'.")
        try:
            res = self.client.send_command(
                "fill_form_fields",
                session_id=session_id,
                parameters={"fields": fields},
                timeout_ms=3000,
            )
            if not res.get("success"):
                raise RuntimeError(res.get("error", "Form fill action rejected by browser."))
            return res.get("data", {})
        except ConnectionError as ce:
            if not self.allow_simulation:
                raise ConnectionError("Browser bridge not connected.") from ce
            return {
                "filled": fields,
                "count": len(fields),
                "requestedCount": len(fields),
                "driverProvenance": "offline_simulation",
                "offlineSimulation": True,
            }

    def get_field_values(
        self, field_names: Optional[List[str]] = None, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Read back field values directly from the active browser tab DOM."""
        try:
            params = {"fieldNames": field_names} if field_names else {}
            res = self.client.send_command(
                "get_field_values",
                session_id=session_id,
                parameters=params,
                timeout_ms=3000,
            )
            if not res.get("success"):
                raise RuntimeError(res.get("error", "Field readback rejected by browser."))
            return res.get("data", {})
        except ConnectionError as ce:
            if not self.allow_simulation:
                raise ConnectionError("Browser bridge not connected.") from ce
            return {"values": {}, "driverProvenance": "offline_simulation", "offlineSimulation": True}

    def click_element(
        self, target_id_or_selector: str, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Click an accessible element on the active browser tab."""
        if str(target_id_or_selector).startswith("@obs-"):
            ref_obs_id = str(target_id_or_selector).split(":")[0][5:]
            if self.latest_observation_id and ref_obs_id != self.latest_observation_id:
                raise ValueError(f"Stale element reference '{target_id_or_selector}': bound to observation '{ref_obs_id}' but active observation is '{self.latest_observation_id}'.")
        try:
            res = self.client.send_command(
                "click_element",
                session_id=session_id,
                parameters={"targetId": target_id_or_selector},
                timeout_ms=3000,
            )
            if not res.get("success"):
                raise RuntimeError(
                    res.get("error", f"Click rejected for target '{target_id_or_selector}'.")
                )
            return res.get("data", {})
        except ConnectionError as ce:
            if not self.allow_simulation:
                raise ConnectionError("Browser bridge not connected.") from ce
            return {"clicked": True, "target": target_id_or_selector, "driverProvenance": "offline_simulation", "offlineSimulation": True}

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
