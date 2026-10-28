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
      const accessibleElements: Array<{
        tag: string;
        type?: string;
        text: string;
        id?: string;
        name?: string;
        role?: string;
        ariaLabel?: string;
        placeholder?: string;
        dataTestId?: string;
      }> = [];
      const interactiveNodes = document.querySelectorAll(
        "button, a[href], input, select, textarea, [role='button'], [role='link'], [role='checkbox'], h1, h2, h3"
      );
      interactiveNodes.forEach((node, idx) => {
        if (idx >= 60) return; // Cap at 60 elements
        const htmlNode = node as HTMLElement;
        const text = (
          htmlNode.innerText ||
          (node as HTMLInputElement).value ||
          (node as HTMLInputElement).placeholder ||
          ""
        ).trim();
        const role = htmlNode.getAttribute("role") || undefined;
        const ariaLabel = htmlNode.getAttribute("aria-label") || undefined;
        const placeholder = (node as HTMLInputElement).placeholder || undefined;
        const name = (node as HTMLInputElement).name || undefined;
        const dataTestId = htmlNode.getAttribute("data-testid") || undefined;

        if (text || htmlNode.id || name || ariaLabel || role) {
          accessibleElements.push({
            tag: htmlNode.tagName.toLowerCase(),
            type: (node as HTMLInputElement).type || undefined,
            text: text.substring(0, 80),
            id: htmlNode.id || undefined,
            name: name || undefined,
            role: role || undefined,
            ariaLabel: ariaLabel || undefined,
            placeholder: placeholder || undefined,
            dataTestId: dataTestId || undefined,
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

  if (request.command === "fill_form_fields") {
    try {
      const fields = (request.fields || request.payload?.fields || {}) as Record<string, string>;
      const filled: Record<string, string> = {};

      for (const [key, value] of Object.entries(fields)) {
        // Try finding by id, then name, then aria-label
        const el = (
          document.getElementById(key) ||
          document.querySelector(`[name="${CSS.escape(key)}"]`) ||
          document.querySelector(`[aria-label="${CSS.escape(key)}"]`) ||
          document.querySelector(`input#${CSS.escape(key)}`) ||
          document.querySelector(`textarea#${CSS.escape(key)}`)
        ) as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null;

        if (el) {
          el.value = String(value);
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
          filled[key] = el.value;
        }
      }

      sendResponse({
        success: true,
        data: {
          filled,
          count: Object.keys(filled).length,
          requestedCount: Object.keys(fields).length,
        },
      });
    } catch (ex: any) {
      sendResponse({ success: false, error: ex.message || "Failed to fill form fields." });
    }
    return true;
  }

  if (request.command === "get_field_values") {
    try {
      const fieldNames = (request.fieldNames || request.payload?.fieldNames) as string[] | undefined;
      const values: Record<string, string> = {};

      if (Array.isArray(fieldNames) && fieldNames.length > 0) {
        for (const name of fieldNames) {
          const el = (
            document.getElementById(name) ||
            document.querySelector(`[name="${CSS.escape(name)}"]`)
          ) as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null;
          if (el) {
            values[name] = el.value;
          }
        }
      } else {
        const inputs = document.querySelectorAll("input, textarea, select");
        inputs.forEach((node) => {
          const inputEl = node as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
          const key = inputEl.id || inputEl.name;
          if (key) {
            values[key] = inputEl.value;
          }
        });
      }

      sendResponse({
        success: true,
        data: { values },
      });
    } catch (ex: any) {
      sendResponse({ success: false, error: ex.message || "Failed to get field values." });
    }
    return true;
  }

  if (request.command === "click_element") {
    try {
      const target =
        request.targetId ||
        request.payload?.targetId ||
        request.selector ||
        request.payload?.selector ||
        request.target;
      let el: HTMLElement | null = null;
      if (target) {
        el =
          document.getElementById(target) ||
          document.querySelector(target) ||
          document.querySelector(`[name="${CSS.escape(target)}"]`) ||
          document.querySelector(`[aria-label="${CSS.escape(target)}"]`) ||
          document.querySelector(`[data-testid="${CSS.escape(target)}"]`);
      }
      if (!el) {
        sendResponse({ success: false, error: `Element '${target}' not found on active page.` });
        return true;
      }
      el.focus();
      el.click();
      sendResponse({
        success: true,
        data: {
          clicked: true,
          tag: el.tagName.toLowerCase(),
          id: el.id,
          text: (el.innerText || "").substring(0, 50),
        },
      });
    } catch (ex: any) {
      sendResponse({ success: false, error: ex.message || "Failed to click element." });
    }
    return true;
  }

  return false;
});

