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
      let sanitizedExcerpt = "";
      const hostname = window.location.hostname.toLowerCase();

      if (hostname.includes("whatsapp.com")) {
        // Targeted privacy minimization for WhatsApp Web:
        // NEVER dump whole innerText (leaking contacts, payment history, private chats).
        // Only observe active conversation title, composer state, and at most the last 2 messages.
        const mainPanel = document.querySelector("#main") || document.querySelector("div[role='region']");
        const headerEl = mainPanel?.querySelector("header") || document.querySelector("header");
        const activeContact = headerEl?.querySelector("span[title]")?.getAttribute("title") || headerEl?.querySelector("div[role='button']")?.textContent?.trim() || "No active conversation selected";
        const composer = document.querySelector("footer div[contenteditable='true']") || document.querySelector("footer");
        const msgNodes = Array.from(document.querySelectorAll("#main div.message-in, #main div.message-out, #main div[data-testid='msg-container']"));
        const recentSnippets = msgNodes.slice(-2).map((m) => {
          const txt = (m as HTMLElement).innerText || "";
          return txt.replace(/\s+/g, " ").trim().substring(0, 150);
        }).filter(Boolean);

        sanitizedExcerpt = [
          `[WhatsApp Web Safe View]`,
          `Active Conversation Contact: ${activeContact}`,
          `Composer Ready: ${composer ? "Yes (contenteditable)" : "No"}`,
          `Recent Conversation Tail (${recentSnippets.length} messages):`,
          ...recentSnippets.map((s, idx) => `  - Msg ${idx + 1}: ${s}`),
        ].join("\n");
      } else if (hostname.includes("linkedin.com")) {
        // Targeted extraction for LinkedIn:
        const profileHeading = document.querySelector(".text-heading-xlarge, h1")?.textContent?.trim() || "";
        const activeChatTitle = document.querySelector(".msg-overlay-bubble-header__title, .msg-entity-lockup__entity-title")?.textContent?.trim() || "";
        const composer = document.querySelector(".msg-form__contenteditable, div[contenteditable='true'][role='textbox']");
        const clone = document.body.cloneNode(true) as HTMLElement;
        clone.querySelectorAll("script, style, noscript, iframe, object, embed, svg").forEach((el) => el.remove());
        const rawText = clone.innerText || "";
        const generalExcerpt = rawText.replace(/\s+/g, " ").trim().substring(0, 4000);

        sanitizedExcerpt = [
          `[LinkedIn View]`,
          `Profile / Header: ${profileHeading || document.title}`,
          `Active Chat Header: ${activeChatTitle || "None"}`,
          `Composer Ready: ${composer ? "Yes" : "No"}`,
          `Page Excerpt:`,
          generalExcerpt,
        ].join("\n");
      } else {
        // Standard sanitized text without script, style, iframe, object, embed
        const clone = document.body.cloneNode(true) as HTMLElement;
        const strippedTags = clone.querySelectorAll("script, style, noscript, iframe, object, embed, svg");
        strippedTags.forEach((el) => el.remove());
        const rawText = clone.innerText || "";
        sanitizedExcerpt = rawText.replace(/\s+/g, " ").trim().substring(0, 15000);
      }

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
        try {
          el = document.querySelector(target);
        } catch {}
        if (!el) {
          el =
            document.getElementById(target) ||
            document.querySelector(`[name="${CSS.escape(target)}"]`) ||
            document.querySelector(`[aria-label="${CSS.escape(target)}"]`) ||
            document.querySelector(`[data-testid="${CSS.escape(target)}"]`);
        }
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

  if (request.command === "input_text") {
    try {
      const text = (request.text || request.payload?.text || request.value || request.payload?.value || "") as string;
      const selector = (request.selector || request.payload?.selector || request.target || request.payload?.target || "") as string;

      let el: HTMLElement | null = null;
      if (selector) {
        try {
          el = document.querySelector(selector);
        } catch {}
      }

      if (!el) {
        // Fallback discovery for active or focused composer/input
        const candidates = [
          "div[contenteditable='true'][role='textbox']",
          "div[contenteditable='true']",
          "footer div[contenteditable='true']",
          "#main footer div[contenteditable='true']",
          ".msg-form__contenteditable",
          "textarea:focus",
          "input:focus",
          "textarea",
          "input[type='text']",
        ];
        for (const cand of candidates) {
          const found = document.querySelector(cand) as HTMLElement | null;
          if (found && found.offsetParent !== null) {
            el = found;
            break;
          }
        }
      }

      if (!el) {
        sendResponse({ success: false, error: "No editable text field or composer found on active page." });
        return true;
      }

      el.focus();

      if (el.isContentEditable || el.getAttribute("contenteditable") === "true") {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        selection?.removeAllRanges();
        selection?.addRange(range);

        const inserted = document.execCommand("insertText", false, text);
        if (!inserted) {
          el.textContent = (el.textContent || "") + text;
        }
        el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        const inputEl = el as HTMLInputElement | HTMLTextAreaElement;
        inputEl.value = text;
        inputEl.dispatchEvent(new Event("input", { bubbles: true }));
        inputEl.dispatchEvent(new Event("change", { bubbles: true }));
      }

      sendResponse({
        success: true,
        data: {
          success: true,
          textTyped: text,
          targetTag: el.tagName.toLowerCase(),
          isContentEditable: el.isContentEditable,
          url: window.location.href,
        },
      });
    } catch (ex: any) {
      sendResponse({ success: false, error: ex.message || "Failed to input text." });
    }
    return true;
  }

  if (request.command === "play_media" || request.command === "play_first_video") {
    try {
      // 1. If video element is already present on page, initiate and verify playback state
      const videoEl = document.querySelector("video") as HTMLVideoElement | null;
      if (videoEl && window.location.href.includes("/watch")) {
        const playPromise = videoEl.play();
        if (playPromise !== undefined) {
          playPromise
            .then(() => {
              const isPlaying = !videoEl.paused && videoEl.readyState >= 2;
              const titleEl = document.querySelector("h1.ytd-watch-metadata yt-formatted-string") || document.querySelector("h1");
              sendResponse({
                success: isPlaying,
                data: {
                  played: isPlaying,
                  playbackState: isPlaying ? "PLAYING" : "BUFFERING",
                  currentTime: videoEl.currentTime,
                  duration: videoEl.duration,
                  title: titleEl?.textContent?.trim() || document.title,
                  url: window.location.href,
                  verifiedPlayback: isPlaying,
                },
              });
            })
            .catch((err) => {
              sendResponse({
                success: false,
                error: `Autoplay restricted or user gesture required: ${err.message}`,
                data: {
                  played: false,
                  playbackState: "RESTRICTED",
                  url: window.location.href,
                },
              });
            });
          return true;
        }
      }

      // 2. Otherwise locate relevant video item from search results
      const videoCandidates = Array.from(
        document.querySelectorAll("ytd-video-renderer a#video-title, ytd-rich-item-renderer a#video-title-link, a[href*='/watch?v=']")
      ) as HTMLAnchorElement[];

      if (videoCandidates.length > 0) {
        const query = (request.query || request.payload?.query || "").toLowerCase();
        let targetLink = videoCandidates[0];
        if (query) {
          const match = videoCandidates.find((c) => (c.getAttribute("title") || c.innerText || "").toLowerCase().includes(query));
          if (match) targetLink = match;
        }

        const title = targetLink.getAttribute("title") || targetLink.innerText || "Media Video";
        const targetUrl = targetLink.href;
        targetLink.click();

        sendResponse({
          success: true,
          data: {
            navigationTriggered: true,
            played: true,
            title,
            url: targetUrl,
            playbackState: "NAVIGATING_TO_PLAYER",
          },
        });
        return true;
      }

      if (videoEl) {
        videoEl.play().catch(() => {});
        sendResponse({
          success: true,
          data: {
            played: !videoEl.paused,
            title: document.title,
            url: window.location.href,
            playbackState: !videoEl.paused ? "PLAYING" : "PAUSED",
          },
        });
        return true;
      }

      sendResponse({ success: false, error: "No playable video element or media links found on current page." });
    } catch (ex: any) {
      sendResponse({ success: false, error: ex.message || "Failed to play media." });
    }
    return true;
  }

  if (request.command === "search_in_tab") {
    try {
      const query = (request.query || request.payload?.query || "") as string;
      if (!query) {
        sendResponse({ success: false, error: "Search query is required." });
        return true;
      }

      const searchSelectors = [
        "input[name='search_query']",
        "input#search",
        "input[name='q']",
        "input[name='k']",
        "input#twotabsearchtextbox",
        "input[type='search']",
        "input[placeholder*='search' i]",
        "input[aria-label*='search' i]",
        "input[data-testid*='search' i]",
        "input[type='text']",
      ];

      let inputEl: HTMLInputElement | null = null;
      for (const sel of searchSelectors) {
        const found = document.querySelector(sel) as HTMLInputElement | null;
        if (found && found.offsetParent !== null) {
          inputEl = found;
          break;
        }
      }

      if (!inputEl) {
        sendResponse({ success: false, error: "No search input found on current page." });
        return true;
      }

      inputEl.focus();
      inputEl.value = query;
      inputEl.dispatchEvent(new Event("input", { bubbles: true }));
      inputEl.dispatchEvent(new Event("change", { bubbles: true }));

      const enterDown = new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true });
      const enterUp = new KeyboardEvent("keyup", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true });
      inputEl.dispatchEvent(enterDown);
      inputEl.dispatchEvent(enterUp);

      if (inputEl.form) {
        try {
          inputEl.form.submit();
        } catch {
          const submitBtn = inputEl.form.querySelector("button[type='submit'], input[type='submit'], button#search-icon-legacy") as HTMLElement | null;
          if (submitBtn) submitBtn.click();
        }
      } else {
        const searchBtn = document.querySelector("button#search-icon-legacy, button[aria-label*='Search' i], button[type='submit']") as HTMLElement | null;
        if (searchBtn) searchBtn.click();
      }

      sendResponse({
        success: true,
        data: {
          query,
          inputFound: true,
          inputSelector: inputEl.tagName.toLowerCase() + (inputEl.id ? "#" + inputEl.id : ""),
          url: window.location.href,
        },
      });
    } catch (ex: any) {
      sendResponse({ success: false, error: ex.message || "Failed to search in tab." });
    }
    return true;
  }

  return false;
});

