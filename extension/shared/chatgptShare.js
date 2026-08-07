/**
 * Recognizes ChatGPT *share* URLs — the only kind the backend's
 * `ChatFetcher` can actually read (a public, unauthenticated page).
 * Private `/c/...` conversation URLs are deliberately NOT matched here,
 * mirroring `ChatFetcher`'s own validation in the backend
 * (`backend/app/services/chat_fetcher.py`). This is still used to decide
 * whether a given URL can be sent straight to the backend — for pasted
 * links in the panel, and to auto-fill the share URL when the injected
 * button is clicked from a page that's already a share link.
 */
const SHARE_URL_PATTERN = /^https:\/\/(chatgpt\.com|chat\.openai\.com)\/share\/[\w-]+\/?(?:[?#].*)?$/;

export function isChatGptShareUrl(url) {
  return typeof url === "string" && SHARE_URL_PATTERN.test(url);
}

/**
 * Recognizes *any* chatgpt.com / chat.openai.com page — private chats,
 * the home page, share links, all of it. This is deliberately broader
 * than `isChatGptShareUrl`: the injected export button should be visible
 * everywhere on ChatGPT, not only on share links, since the panel now
 * offers a way to paste a share link manually (see the panel's
 * "Load a shared conversation" card) — so there's no reason to hide the
 * entry point just because the current page happens not to be one.
 */
const CHATGPT_HOST_PATTERN = /^https:\/\/(chatgpt\.com|chat\.openai\.com)(\/.*)?$/;

export function isChatGptPage(url) {
  return typeof url === "string" && CHATGPT_HOST_PATTERN.test(url);
}
