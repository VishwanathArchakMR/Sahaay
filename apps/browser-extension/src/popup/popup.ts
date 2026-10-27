/**
 * Popup script for Sahaay Extension.
 */

const btnInspect = document.getElementById("btn-inspect") as HTMLButtonElement;
const btnScroll = document.getElementById("btn-scroll") as HTMLButtonElement;
const resultBox = document.getElementById("result-box") as HTMLDivElement;
const hostBadge = document.getElementById("host-badge") as HTMLSpanElement;

btnInspect?.addEventListener("click", () => {
  resultBox.textContent = "Inspecting tab...";
  chrome.runtime.sendMessage(
    {
      command: "get_tab_observation",
      sessionId: "popup-session",
    },
    (res) => {
      if (!res || !res.success) {
        resultBox.textContent = `Error: ${res?.error || "Inspection failed."}`;
        hostBadge.className = "badge badge-warn";
        hostBadge.textContent = "Error";
        return;
      }

      hostBadge.className = "badge";
      hostBadge.textContent = "Observed";
      const data = res.data;
      resultBox.innerHTML = `
        <strong>Title:</strong> ${data.title}<br/>
        <strong>URL:</strong> ${data.url}<br/>
        <strong>Scroll:</strong> (${data.scrollPosition.x}, ${data.scrollPosition.y})<br/>
        <strong>Height:</strong> ${data.documentDimensions.scrollHeight}px<br/>
        <strong>Controls Found:</strong> ${data.accessibleElements?.length || 0}<br/>
        <strong>Excerpt:</strong> ${data.visibleTextExcerpt.substring(0, 150)}...
      `;
    }
  );
});

btnScroll?.addEventListener("click", () => {
  resultBox.textContent = "Executing scroll action (+300px)...";
  chrome.runtime.sendMessage(
    {
      command: "scroll_tab",
      sessionId: "popup-session",
      payload: { deltaY: 300 },
    },
    (res) => {
      if (!res || !res.success) {
        resultBox.textContent = `Error: ${res?.error || "Scroll failed."}`;
        return;
      }
      const data = res.data;
      resultBox.innerHTML = `
        <strong>Scroll Action:</strong> Success<br/>
        <strong>Pre Scroll:</strong> ${data.preScrollY}px<br/>
        <strong>Post Scroll:</strong> ${data.postScrollY}px<br/>
        <strong>Delta:</strong> ${data.actualDeltaY}px (Requested: ${data.requestedDeltaY}px)
      `;
    }
  );
});
