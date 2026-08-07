/**
 * Content script: injects a floating "Export with ChatBook" button on
 * every ChatGPT page — not just share links, since the panel now offers
 * a way to paste a share link manually, so there's no reason to hide the
 * entry point elsewhere on the site. Its only job is detection + a
 * button; all of the actual work (fetching, parsing, PDF generation)
 * happens in the export panel via the existing backend API — this file
 * never touches any of that logic. Shared verbatim between the Chrome
 * and Safari builds.
 *
 * Deliberately NOT an ES module, unlike the rest of shared/ — content
 * scripts are the one place where "type": "module" support is a narrower,
 * more optional manifest field than the module usage elsewhere in this
 * project (background.js's service worker module, which MV3 itself
 * depends on, and panel.js's plain `<script type="module">` in a normal
 * loaded HTML page, which has been standard since Safari 10.1). Whether
 * WebKit's content-script loader honors that field can't be confirmed
 * without running real Safari, which isn't available here — so rather
 * than risk the button silently never appearing on Safari, this file
 * inlines its only two dependencies (both a few lines) and stays a
 * classic script, which is guaranteed to load on every browser/version.
 */
(function () {
  // Mirrors shared/chatgptShare.js's isChatGptShareUrl() and
  // isChatGptPage() — see that file for why the two are kept separate:
  // the button shows on any ChatGPT page, but only a share link can
  // actually be sent to the backend.
  const SHARE_URL_PATTERN = /^https:\/\/(chatgpt\.com|chat\.openai\.com)\/share\/[\w-]+\/?(?:[?#].*)?$/;
  function isChatGptShareUrl(url) {
    return typeof url === "string" && SHARE_URL_PATTERN.test(url);
  }

  const CHATGPT_HOST_PATTERN = /^https:\/\/(chatgpt\.com|chat\.openai\.com)(\/.*)?$/;
  function isChatGptPage(url) {
    return typeof url === "string" && CHATGPT_HOST_PATTERN.test(url);
  }

  // Mirrors shared/lib/browser-api.js's cross-browser shim.
  const browserAPI = globalThis.browser ?? globalThis.chrome;

  const BUTTON_HOST_ID = "gpttopdf-export-button-host";

  function injectButton() {
    if (!isChatGptPage(window.location.href)) return;
    if (document.getElementById(BUTTON_HOST_ID)) return; // already injected

    const host = document.createElement("div");
    host.id = BUTTON_HOST_ID;
    host.style.position = "fixed";
    // Sits at roughly the same height as ChatGPT's own composer row, just
    // clear of the very corner — floating it well above the composer
    // (like a separate banner in empty space) read as more out of place
    // than sitting flush in the corner did.
    host.style.bottom = "28px";
    host.style.right = "32px";
    host.style.zIndex = "2147483647"; // stay above ChatGPT's own UI

    // A shadow root keeps ChatGPT's stylesheet from bleeding into the
    // button (and this button's styles from ever touching the host page).
    const shadow = host.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = `
      @keyframes gpttopdf-rise {
        from { opacity: 0; transform: translateY(10px) scale(0.8); }
        to { opacity: 1; transform: translateY(0) scale(1); }
      }
      /* No circle, no card, no border — just the logo itself, sitting
         directly on the page like a mark that belongs there, not a UI
         chrome element wrapped around it. */
      .btn {
        display: block;
        width: 52px;
        height: 52px;
        padding: 0;
        border: none;
        background: transparent;
        cursor: pointer;
        transition: transform 0.15s cubic-bezier(0.16, 1, 0.3, 1), filter 0.15s cubic-bezier(0.16, 1, 0.3, 1);
        animation: gpttopdf-rise 0.28s cubic-bezier(0.16, 1, 0.3, 1) both;
      }
      .btn:hover {
        transform: translateY(-2px) scale(1.06);
        filter: drop-shadow(0 6px 16px rgba(0, 0, 0, 0.45)) drop-shadow(0 0 14px rgba(56, 189, 248, 0.4));
      }
      .btn:active { transform: translateY(0) scale(0.95); }
      .btn img {
        width: 100%;
        height: 100%;
        display: block;
        pointer-events: none;
        filter: drop-shadow(0 4px 10px rgba(0, 0, 0, 0.4));
      }
      /* Played once on click, right before the panel opens — a quick
         squash-and-glow "launch" so the click reads as having triggered
         something, since the actual panel-opening motion (native slide-in
         on Chrome, window creation on Safari) is outside this button's
         control. */
      @keyframes gpttopdf-launch {
        0% { transform: scale(1); }
        35% { transform: scale(0.86); }
        70% { transform: scale(1.14); }
        100% { transform: scale(1); }
      }
      .btn.launching { animation: gpttopdf-launch 420ms cubic-bezier(0.16, 1, 0.3, 1); }
    `;
    shadow.appendChild(style);

    // A content script runs in the host page's context, so a plain
    // relative path would resolve against chatgpt.com, not the
    // extension's own package — runtime.getURL() is what gives back the
    // real chrome-extension://... / safari-web-extension://... URL.
    // The logo is a plain SVG — no manifest involved here, no need to
    // rasterize it, an <img> renders it directly like any other image.
    const logoUrl = browserAPI.runtime.getURL("icons/logo.svg");

    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn";
    button.title = "Export with ChatBook";
    button.setAttribute("aria-label", "Export with ChatBook");
    button.innerHTML = `<img src="${logoUrl}" alt="" />`;
    button.addEventListener("click", () => {
      // "Export panel" rather than "side panel": on Chrome this opens a
      // native docked side panel; on Safari (no such API) the background
      // worker falls back to a positioned popup window. The content
      // script doesn't need to know or care which — that's handled in
      // shared/background/background.js.
      //
      // Only pass the current URL along as the share URL if it actually
      // is one — the button now shows on every ChatGPT page, including
      // private /c/... chats, so on any page that isn't a share link the
      // panel should just open to its normal "paste a link, or open one
      // in a new tab" choice instead of trying to auto-load a URL the
      // backend can't read.
      button.classList.remove("launching");
      // Force a reflow so re-clicking mid-animation restarts it instead of
      // being a no-op (classList.add alone would do nothing if the class
      // is already present from a previous, still-finishing click).
      void button.offsetWidth;
      button.classList.add("launching");

      const currentUrl = window.location.href;
      browserAPI.runtime.sendMessage({
        type: "OPEN_EXPORT_PANEL",
        shareUrl: isChatGptShareUrl(currentUrl) ? currentUrl : null,
      });
    });

    shadow.appendChild(button);
    document.documentElement.appendChild(host);
  }

  injectButton();

  // Share pages are effectively static, but this is a cheap,
  // self-correcting safeguard in case ChatGPT's own React app re-renders
  // and wipes an ancestor node the button was attached to shortly after
  // page load — it's a no-op once the button already exists.
  const observer = new MutationObserver(() => injectButton());
  observer.observe(document.documentElement, { childList: true, subtree: false });
})();
