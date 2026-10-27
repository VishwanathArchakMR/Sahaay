/**
 * Sahaay Content Script for Authorized Browser Tabs.
 * Sandboxed in webpage context, extracts sanitized text without exposing native bridges.
 * Implements bounded, verified actions (e.g. scroll_tab).
 */

console.log("[Sahaay Content] Injected into authorized tab:", window.location.href);

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (!request || !request.command) return false;

  if (request.command === "get_sanitized_dom" || request.command === "get_tab_observation") {
    try {
      // 1. Extract sanitized text without script, style, iframe, object, embed
      const clone = document.body.cloneNode(true) as HTMLElement;
      const strippedTags = clone.querySelectorAll("script, style, noscript, iframe, object, embed, svg");
      strippedTags.forEach((el) => el.remove());
      const rawText = clone.innerText || "";
      const sanitizedExcerpt = rawText.replace(/\s+/g, " ").trim().substring(0, 15000);

      // 2. Discover accessible interactive controls (buttons, links, inputs, headings)
      const accessibleElements: Array<{ tag: string; type?: string; text: string; id?: string }> = [];
      const interactiveNodes = document.querySelectorAll("button, a[href], input, select, textarea, h1, h2, h3");
      interactiveNodes.forEach((node, idx) => {
        if (idx >= 40) return; // Cap at 40 elements
        const htmlNode = node as HTMLElement;
        const text = (htmlNode.innerText || (node as HTMLInputElement).value || (node as HTMLInputElement).placeholder || "").trim();
        if (text || htmlNode.id) {
          accessibleElements.push({
            tag: htmlNode.tagName.toLowerCase(),
            type: (node as HTMLInputElement).type || undefined,
            text: text.substring(0, 80),
            id: htmlNode.id || undefined,
          });
        }
      });

      sendResponse({
        success: true,
        data: {
          url: window.location.href,
          title: document.title,
          scrollPosition: { x: window.scrollX, y: window.scrollY },
          documentDimensions: {
            scrollHeight: document.documentElement.scrollHeight,
            clientHeight: document.documentElement.clientHeight,
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
          },
          visibleTextExcerpt: sanitizedExcerpt,
          accessibleElements,
        },
      });
    } catch (ex: any) {
      sendResponse({ success: false, error: ex.message || "Failed to inspect page DOM." });
    }
    return true;
  }

  if (request.command === "scroll_tab") {
    try {
      const deltaY = typeof request.deltaY === "number" ? request.deltaY : 300;
      const preScrollY = window.scrollY;

      window.scrollBy({ top: deltaY, left: 0, behavior: "instant" });
      const postScrollY = window.scrollY;

      sendResponse({
        success: true,
        data: {
          preScrollY,
          postScrollY,
          requestedDeltaY: deltaY,
          actualDeltaY: postScrollY - preScrollY,
        },
      });
    } catch (ex: any) {
      sendResponse({ success: false, error: ex.message || "Failed to execute scroll action." });
    }
    return true;
  }

  return false;
});
