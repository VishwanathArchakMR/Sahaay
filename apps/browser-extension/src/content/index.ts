/**
 * Content script for Sahaay Browser Extension.
 * Sandboxed in webpage context, extracts sanitized text without exposing native bridges.
 */

console.log("Sahaay Content Script injected into authorized tab.");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request && request.command === "get_sanitized_dom") {
    // Return sanitized text content without script/style tags or raw cookies
    const clonedBody = document.body.cloneNode(true) as HTMLElement;
    const scripts = clonedBody.querySelectorAll("script, style, iframe, object, embed");
    scripts.forEach((el) => el.remove());

    sendResponse({
      success: true,
      textExcerpt: clonedBody.innerText.substring(0, 50000),
      url: window.location.href,
      title: document.title,
    });
    return true;
  }
});
