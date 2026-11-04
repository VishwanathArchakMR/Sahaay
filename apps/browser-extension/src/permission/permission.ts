// Permission handler for Sahaay Voice Input

const btnRequest = document.getElementById("btn-request") as HTMLButtonElement | null;
const statusMsg = document.getElementById("status-msg") as HTMLDivElement | null;

if (btnRequest && statusMsg) {
  btnRequest.addEventListener("click", async () => {
    btnRequest.disabled = true;
    btnRequest.textContent = "Requesting permission...";
    statusMsg.className = "status-msg";
    statusMsg.textContent = "";

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Immediately stop audio tracks once granted
      stream.getTracks().forEach((track) => track.stop());

      statusMsg.className = "status-msg status-success";
      statusMsg.textContent = "✓ Microphone permission granted! Closing this tab...";
      btnRequest.textContent = "Permission Granted";

      // Notify any active sidepanel instances
      try {
        chrome.runtime.sendMessage({ type: "VOICE_PERMISSION_GRANTED" });
      } catch {}

      // Auto-close after 1.2 seconds
      setTimeout(() => {
        window.close();
      }, 1200);
    } catch (err: any) {
      btnRequest.disabled = false;
      btnRequest.textContent = "Retry Permission Request";
      statusMsg.className = "status-msg status-error";
      statusMsg.textContent = `Permission denied: ${err?.message || "Please click the camera/mic icon in the browser address bar to allow microphone access."}`;
    }
  });
}
