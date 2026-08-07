# ChatBook — Browser Extension (Chrome + Safari)

Adds an "Export with ChatBook" button to ChatGPT shared-conversation
pages, opening a panel that turns the conversation into a PDF — using
the exact same backend as the main web app. Ships for both Chrome and
Safari from one shared codebase.

## Architecture: one shared codebase, two thin platform shells

```
extension/
  shared/                  <- edit this. Used verbatim by both platforms.
    lib/
      browser-api.js        Cross-browser chrome.*/browser.* shim
    config.js                BACKEND_BASE_URL
    chatgptShare.js          isChatGptShareUrl() — share-URL matcher
    content/
      content-script.js     Injects the button (Shadow DOM)
    background/
      background.js         Opens the panel; feature-detects sidePanel
    panel/
      panel.html / .css / .js   The panel UI (vanilla JS, no framework)
      api.js                 Thin fetch wrapper -> existing backend
    icons/                   16/32/48/128px icons, used by both builds

  chrome/
    manifest.json            Chrome-only: side_panel + sidePanel permission

  safari/
    manifest.json            Safari-only: no side_panel key/permission

  scripts/
    build.js                 Assembles dist/<platform>/ (no dependencies)

  dist/                       <- generated, not hand-edited
    chrome/                   Point Chrome's "Load unpacked" here
    safari/                   Feed this to Safari's extension converter
```

Every behavioral difference between platforms is handled by **one**
runtime feature-detection in `shared/background/background.js`, not by
forking any file:

- **API namespace.** `shared/lib/browser-api.js` exports `browserAPI =
  globalThis.browser ?? globalThis.chrome`. Safari and Firefox define the
  standard, Promise-based `browser.*`; Chrome only defines `chrome.*`
  (which also resolves Promises in MV3 when no callback is passed). Every
  shared file imports `browserAPI` from here instead of touching either
  global directly, so the same file runs unmodified on both platforms.
- **Side panel.** Chrome (and other Chromium browsers) expose a native
  docked `chrome.sidePanel` API. Safari has no equivalent — there is no
  docked-panel API in WebKit's extension model as of this writing.
  `background.js` checks `browserAPI.sidePanel?.open` at runtime: if it
  exists, it opens the real docked side panel (Chrome); if not, it opens
  the identical `panel.html` in a compact popup window pinned to the
  right edge of the current window (Safari) — the closest available
  approximation to a sidebar. Same panel UI, same code, different
  container.

Because Chrome and Safari both require every file a manifest references
to live *inside* the extension's own root folder (neither will resolve a
`../shared/x.js` path reaching outside it), `scripts/build.js` copies
`shared/` plus the chosen platform's `manifest.json` into
`dist/<platform>/` before you load or package it. This is the one build
step in an otherwise buildless project — plain Node `fs`, nothing to
`npm install`.

**Whenever you edit anything under `shared/`, re-run the build:**

```bash
node scripts/build.js          # rebuilds dist/chrome and dist/safari
node scripts/build.js chrome   # or just one platform
```

## Panel design

The panel (`shared/panel/`) is a Notion/Raycast/Arc-inspired UI, not a
plain popup:

- **Dark mode by default**, following system preference on first run and
  remembering a manual toggle (top-right of the header) via
  `storage.local`.
- **Command-bar search** over the section list (`⌘K` to focus it),
  filtering client-side only — it never changes what's sent to the
  backend.
- **Keyboard shortcuts**: `⌘K` search, `⌘A` select all, `⌘⌫`/`⌘D`
  deselect all, `⌘↵` generate, arrow keys + space to navigate/toggle
  rows, `Esc` to blur search or (on Safari's popup fallback) close the
  panel. A footer hint bar shows the active ones.
- **Loading skeletons** (shimmering placeholder rows) while parsing,
  a top indeterminate progress bar during parsing/generating, and short
  fade/slide-in animations on new content — all skipped automatically
  under `prefers-reduced-motion`.
- **Responsive** down to ~300px wide, since Chrome's side panel is
  user-resizable and Safari's fallback is a fixed-width popup.
- **Two ways to load a conversation**, shown together on the idle screen:
  paste a share link directly into the panel (validated with the same
  `isChatGptShareUrl` check used elsewhere), which works from any tab —
  including the private `chatgpt.com/c/...` conversation itself, with no
  need to open the share link in a new tab at all — or open that link in
  a new tab, where the injected page button still works as before. A
  failed load re-shows this form so a mistyped link is easy to fix.
- **The export button shows on every ChatGPT page**, not just share
  links — home page, private `/c/...` chats, all of it — since the panel
  always lets you choose how to proceed. Clicking it on an actual share
  link still auto-loads that conversation immediately (no extra clicks);
  clicking it anywhere else just opens the panel to the same "paste a
  link, or open one in a new tab" choice above, rather than trying to
  auto-load a URL the backend can't read. See `isChatGptPage` vs.
  `isChatGptShareUrl` in `shared/chatgptShare.js` for the distinction.

None of this touches `shared/panel/api.js`, `shared/config.js`, or the
backend — it's a UI-only layer on top of the same two API calls.

## Icons

`shared/icons/` holds two different things, generated two different ways:

- **`logo.svg`** — a verbatim copy of the project's `logo.svg`, used
  directly (plain `<img src="...">`, no conversion at all) by the panel
  header and the injected page button. Both render inside a normal DOM
  that supports SVG natively, so there's nothing to generate here.
- **`icon16/32/48/128.png`** — the one place a raw copy of `logo.svg`
  can't be used: Chrome's and Safari's manifest `icons`/`action.default_icon`
  fields are a hard platform requirement for a *raster* image, full stop,
  regardless of how the source art is authored. `logo.svg` itself isn't
  real vector paths — it's an SVG wrapper around two embedded raster
  layers (a white silhouette mask plus a rainbow-gradient color layer,
  composited via an SVG filter), which is why it's ~370KB and why tools
  without full SVG-filter support (this sandbox's ImageMagick, notably)
  render it as a blank/broken image. Regenerating the PNGs means
  extracting and recombining those two layers directly rather than
  asking an SVG renderer to do it:

  1. Extract both `data:image/png;base64,...` payloads from the SVG
     (`xlink:href` attributes on its two `<image>` elements).
  2. Use the white-on-transparent one as an alpha mask and the
     full-color one as the RGB source — `Image.putalpha()` on the color
     layer with the mask reconstructs the correct transparent PNG.
  3. Pad it to a square canvas (its native size is portrait, ~1343×1604)
     with a little breathing room, centered, rather than cropping or
     stretching.
  4. Downsample to 128/48/32/16 with `Image.LANCZOS`.

  This mark is bold and high-contrast enough that it holds up at every
  size without needing any further per-size stroke adjustments —
  verified by actually rendering each output size before finalizing, not
  just assumed from the source looking fine at full resolution.

If the source `logo.svg` ever changes, replace `shared/icons/logo.svg`
with the new file directly, and only regenerate the four PNGs (steps
1–4 above) — nothing else in this directory needs touching.

## Try it on Chrome

1. Run the backend locally (`cd backend && uvicorn app.main:app --reload`)
   — the panel talks to `http://localhost:8000/api` by default (see
   `shared/config.js`).
2. `node scripts/build.js chrome`
3. Open `chrome://extensions`, enable **Developer mode**, click
   **Load unpacked**, and select `extension/dist/chrome`.
4. Open any chatgpt.com page — the "Export with ChatBook" button appears
   bottom-right within a second. Click it: from a share link
   (`https://chatgpt.com/share/<id>`) this loads that conversation
   immediately; from anywhere else (including a private `/c/...` chat) it
   opens the panel to the paste-a-link / open-in-a-new-tab choice
   instead.

## Package it for Safari

Safari extensions can't be "loaded unpacked" the way Chrome's can — they
must be wrapped in a signed native macOS (and optionally iOS) app and run
through Xcode. This step has to happen on a Mac with Xcode installed;
none of it can be done from here.

1. **Build the Safari bundle:**
   ```bash
   node scripts/build.js safari
   ```
2. **Install Xcode** (from the Mac App Store) if you don't have it, plus
   its command line tools: `xcode-select --install`.
3. **Convert it into an Xcode project** using Apple's official converter,
   pointed at the folder the build step just produced:
   ```bash
   xcrun safari-web-extension-converter extension/dist/safari \
     --project-location ./extension/safari-xcode \
     --app-name "ChatBook" \
     --bundle-identifier com.yourname.chatbook
   ```
   This scaffolds a full Xcode project with a thin native app target that
   just hosts your web extension (icons, entitlements, and asset catalog
   are generated for you — you don't need to touch Swift/Xcode UI code).
4. **Open the generated `.xcodeproj` in Xcode**, select your Apple
   Developer Team under the target's Signing & Capabilities tab (a free
   personal team works for local testing), and hit **Run** (⌘R). This
   launches the thin host app once, which registers the extension with
   Safari.
5. **Enable it in Safari:** Safari → Settings → Extensions → turn on
   "ChatBook". For an unsigned/development build, you'll also need
   Safari's Develop menu → "Allow Unsigned Extensions" (enable the
   Develop menu first via Safari → Settings → Advanced, if you don't see
   it).
6. **Test it** the same way as Chrome: open a `chatgpt.com/share/...`
   page. The first time, Safari will prompt you to grant the extension
   permission for that site — this per-site consent prompt is stricter
   than Chrome's and is expected, not a bug.

**Safari-specific hardening already done, since none of it can be tested
from this environment (no macOS/Xcode/Safari available here):**

- The content script (`shared/content/content-script.js`) is deliberately
  a classic script, not an ES module, even though every other shared file
  is. Chrome's support for `"type": "module"` content scripts is solid;
  WebKit's is a narrower, more optional manifest field whose behavior
  can't be confirmed without running real Safari, and if it weren't
  honored, the export button would silently never appear on Safari at
  all. Its two tiny dependencies are inlined instead so it can't be
  affected either way.
- The share-URL handoff from content script → panel uses `storage.local`,
  not `storage.session`. `storage.session` is a newer, Chrome-originated
  addition to the WebExtensions storage API; `storage.local` is part of
  the original API and its cross-browser support is far better
  established. The handoff doesn't need session-only semantics anyway.
- `background.js` opens the panel as the very first call in its message
  listener, before the storage write — Chrome requires `sidePanel.open()`
  to be the first async call in a gesture-triggered handler, and getting
  this wrong is a common source of "may only be called in response to a
  user gesture" errors.

These are defensive choices based on what's documented about
cross-browser WebExtensions support, not confirmed by an actual Safari
run. If you hit an error when testing in Xcode, check the Safari Web
Inspector's console on the panel/background contexts first — that'll
point at whichever of these assumptions (if any) doesn't hold.

**Version requirement:** this manifest uses Manifest V3 with a
service-worker background script, which Safari supports from **Safari
16.4 / macOS 13 Ventura** onward (and the corresponding iOS/iPadOS 16.4+
for a Safari Web Extension on those platforms). Older Safari versions
only support Manifest V2 with a persistent background page, which this
codebase does not target.

**Distributing beyond your own Mac** requires archiving the app in
Xcode and either notarizing it for direct (Developer ID) distribution on
macOS 13+, or submitting the whole app through App Store Connect for the
Mac App Store — Safari has no unpacked/"developer mode" install path for
end users the way Chrome does.

## Before shipping either build to real users

- **Deploy the backend somewhere public** and update `BACKEND_BASE_URL`
  in `shared/config.js` — `localhost:8000` only works on the machine
  running that server. Rebuild after changing it.
- The backend's CORS config (`backend/app/main.py`) already allows both
  `chrome-extension://` and `safari-web-extension://` origins via
  `allow_origin_regex=r"(chrome|safari-web)-extension://.*"`. This is
  needed even for local testing, not just public deployment — Safari's
  panel runs from a `safari-web-extension://` origin from the very first
  time you load it, and that origin needs this regex to reach
  `localhost:8000` at all.
- `shared/icons/` icons are derived from the project's `logo.svg` (see
  "Icons" above) — regenerate the four PNGs the same way if that source
  logo ever changes; `logo.svg` itself just needs replacing verbatim.
- `extension/dist/` and `extension/safari-xcode/` are both generated and
  already excluded via the repo's root `.gitignore`.

## Reuse boundary

No parser or PDF-generation logic lives anywhere in this folder — that
stays exactly once, server-side, in `backend/app/parsers/` and
`backend/app/pdf/`. `shared/panel/api.js` is a thin fetch wrapper around
the same two endpoints the main frontend already calls
(`frontend/src/services/api/*`); duplicating that few-line wrapper is
unavoidable for any second client talking to the same API, but the
actual work stays single-sourced. Between the two extension platforms
themselves, reuse is total: every line of behavior lives in `shared/`,
and `chrome/manifest.json` / `safari/manifest.json` are the only
platform-specific files in the whole project.
