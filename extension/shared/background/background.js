/**
 * Background service worker — shared verbatim between the Chrome and
 * Safari builds.
 *
 * Two jobs, both just plumbing — no parsing/PDF logic lives here:
 *
 *  1. Let clicking the toolbar icon open the export panel directly, as an
 *     alternate entry point to the injected page button.
 *  2. Relay "open the export panel for this tab, with this share URL"
 *     requests from the content script — only a user-gesture-triggered
 *     handler in a trusted extension context (background, not the
 *     content script itself) is allowed to open a side panel / window.
 *
 * The share URL is handed to the panel via `storage.local` rather than a
 * direct runtime message, because the panel document doesn't exist yet
 * at the moment the button is clicked — opening it is what creates it —
 * so there's nothing listening for a message yet. Storage is the
 * simplest way to pass data to a page that isn't loaded. `storage.local`
 * rather than the newer `storage.session` deliberately: this handoff
 * doesn't need session-only semantics, and `local` is part of the
 * original WebExtensions storage API rather than a more recent,
 * Chrome-originated addition whose Safari support isn't confirmed.
 *
 * Platform difference this file absorbs: Chrome (and other Chromium
 * browsers) expose a native docked `sidePanel` API; Safari does not
 * define one at all as of this writing. Rather than fork this file per
 * platform, we feature-detect at runtime and fall back to a compact
 * popup window positioned like a sidebar on any browser without
 * `sidePanel` support — see `openPanel()` below.
 */
import { browserAPI } from "../lib/browser-api.js";

browserAPI.runtime.onInstalled.addListener(() => {
  browserAPI.sidePanel
    ?.setPanelBehavior({ openPanelOnActionClick: true })
    .catch(() => {
      // Older Chrome versions without this API, or a browser (Safari)
      // that doesn't have it at all: the injected page button and the
      // toolbar-click fallback below remain the entry points.
    });
});

browserAPI.runtime.onMessage.addListener((message, sender) => {
  if (message?.type !== "OPEN_EXPORT_PANEL") return;

  const tabId = sender.tab?.id;
  if (tabId == null) return;

  // Chrome only honors `sidePanel.open()`'s user-gesture requirement
  // (inherited here from the content script's button click) if it's the
  // first async call made in this listener — awaiting anything else
  // first (e.g. the storage write below) can make Chrome reject the call
  // with "may only be called in response to a user gesture". So fire
  // `openPanel()` immediately and let the storage write happen alongside
  // it rather than gating one behind the other; the panel's
  // `storage.onChanged` listener (panel.js) catches the share URL even
  // if it arrives a tick after the panel has already mounted.
  openPanel(tabId);
  // message.shareUrl is null when the click came from a ChatGPT page that
  // isn't a share link (see content-script.js) — storing null here (not
  // skipping the write) is intentional, so a stale share URL from an
  // earlier click doesn't get auto-loaded into a panel opened fresh from
  // a different, non-share page.
  browserAPI.storage.local.set({ shareUrl: message.shareUrl ?? null });
});

// On Chrome, `setPanelBehavior({ openPanelOnActionClick: true })` above
// means the toolbar icon opens the side panel natively and this listener
// never fires. On Safari (no `sidePanel` API, so that call above never
// even attempted), this is the toolbar icon's only handler.
browserAPI.action?.onClicked.addListener((tab) => {
  if (!browserAPI.sidePanel && tab.id != null) openPanel(tab.id);
});

async function openPanel(tabId) {
  if (browserAPI.sidePanel?.open) {
    await browserAPI.sidePanel.open({ tabId });
    return;
  }

  // Safari fallback: there's no docked side panel API, so open the same
  // panel UI as a compact popup window pinned to the right edge of the
  // current window — the closest approximation to a sidebar available.
  const current = await browserAPI.windows.getCurrent();
  const width = 420;
  await browserAPI.windows.create({
    url: browserAPI.runtime.getURL("panel/panel.html"),
    type: "popup",
    width,
    height: current.height ?? 800,
    left: (current.left ?? 0) + (current.width ?? 1280) - width,
    top: current.top ?? 0,
  });
}
