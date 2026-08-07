/**
 * Cross-browser extension API shim.
 *
 * Chrome/Edge expose `chrome.*` (callback-based historically, but modern
 * MV3 APIs also resolve a Promise when no callback is passed). Safari and
 * Firefox expose the standard, Promise-native `browser.*` namespace, and
 * Safari additionally aliases `chrome.*` to the same implementation for
 * drop-in compatibility.
 *
 * Every shared file imports `browserAPI` from here instead of touching
 * `chrome` or `browser` directly, so the same background/content/panel
 * code runs unmodified on both platforms. Prefer `browser` when present
 * (guaranteed Promise-based); fall back to `chrome` (Chrome/Edge, and any
 * other browser that only defines that name).
 */
export const browserAPI = globalThis.browser ?? globalThis.chrome;
