/**
 * Export panel app. Vanilla JS on purpose — no framework/build step, so
 * the extension loads directly via "Load unpacked" (Chrome) or feeds
 * straight into the Xcode converter (Safari) with nothing to compile.
 * All real work (fetching, parsing, PDF rendering) happens server-side
 * through the two calls in `api.js`; this file is purely UI state, theme,
 * keyboard shortcuts, and animation. Shared verbatim between the Chrome
 * and Safari builds.
 */
import { parseConversation, generatePdf, ApiError } from "./api.js";
import { browserAPI } from "../lib/browser-api.js";
import { isChatGptShareUrl } from "../chatgptShare.js";

const app = document.getElementById("app");
const header = document.querySelector(".header");
const progressBar = document.getElementById("progressBar");
const themeToggle = document.getElementById("themeToggle");
const themeIcon = document.getElementById("themeIcon");

// ---------- Entrance animation ----------
//
// Chrome doesn't always tear down and reload a docked side panel's
// document when you close and reopen it — it can keep the same page
// alive in the background and just toggle visibility. A CSS `animation`
// declared directly on a selector only ever plays once, the first time
// that document loads, so on every *later* open the "arriving" motion
// would silently never happen again. Driving it from a JS-toggled class
// instead lets it replay on every real appearance: once on initial load,
// and again whenever the document comes back from hidden to visible.
function playEntranceAnimation() {
  [document.body, header, app].forEach((el) => {
    if (!el) return;
    el.classList.remove("panel-enter");
    void el.offsetWidth; // force reflow so re-adding the class restarts the animation
    el.classList.add("panel-enter");
  });
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") playEntranceAnimation();
});
window.addEventListener("pageshow", playEntranceAnimation);

const THEME_STORAGE_KEY = "theme";
const LOADING_STATUSES = new Set(["parsing", "generating"]);

const state = {
  shareUrl: null,
  conversation: null,
  selectedIds: new Set(),
  status: "idle", // idle | parsing | ready-to-select | generating | pdf-ready | error
  error: null,
  pdfUrl: null,
  filterQuery: "",
};

// ---------- Theme (dark by default, remembers manual choice, follows
// system preference otherwise) ----------

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  themeIcon.textContent = theme === "dark" ? "🌙" : "☀️";
}

async function initTheme() {
  let saved;
  try {
    const result = await browserAPI.storage.local.get(THEME_STORAGE_KEY);
    saved = result?.[THEME_STORAGE_KEY];
  } catch {
    saved = undefined;
  }
  const theme = saved ?? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  applyTheme(theme);
}

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  applyTheme(next);
  browserAPI.storage.local.set({ [THEME_STORAGE_KEY]: next }).catch(() => {});
});

// ---------- Status: drives the top loading bar + footer shortcut bar
// (both keyed off `body[data-status]` in panel.css) ----------

function setStatus(status) {
  state.status = status;
  document.body.dataset.status = status;
  progressBar.classList.toggle("hidden", !LOADING_STATUSES.has(status));
}

// ---------- Rendering ----------

function render() {
  app.innerHTML = "";

  if (state.status === "idle") {
    app.appendChild(renderEmptyState({ prefillUrl: state.shareUrl || "" }));
    return;
  }

  if (state.shareUrl && state.status !== "parsing" && state.status !== "idle") {
    const urlRow = document.createElement("div");
    urlRow.className = "share-url-row animate-in";

    const urlBlock = document.createElement("p");
    urlBlock.className = "share-url";
    urlBlock.textContent = state.shareUrl;
    urlRow.appendChild(urlBlock);

    // Once a conversation is loaded there was previously no way back to
    // try a different link short of closing and reopening the panel.
    // This returns to the paste-a-link screen (prefilled with the current
    // URL so it's an edit, not a retype) without losing anything else.
    const changeBtn = document.createElement("button");
    changeBtn.type = "button";
    changeBtn.className = "link-btn share-url-change";
    changeBtn.textContent = "Change link";
    changeBtn.disabled = state.status === "generating";
    changeBtn.addEventListener("click", handleChangeUrl);
    urlRow.appendChild(changeBtn);

    app.appendChild(urlRow);
  }

  if (state.status === "parsing") {
    app.appendChild(renderSkeleton());
    return;
  }

  if (state.status === "error") {
    app.appendChild(renderEmptyState({ error: state.error }));
    return;
  }

  if (state.status === "ready-to-select" && state.conversation) {
    app.appendChild(renderSectionPicker());
    return;
  }

  if (state.status === "generating") {
    app.appendChild(renderSectionPicker({ disabled: true }));
    app.appendChild(
      renderCard(
        `<p class="state-message loading-dots">Generating your PDF<span>.</span><span>.</span><span>.</span></p>`,
        "animate-in"
      )
    );
    return;
  }

  if (state.status === "pdf-ready" && state.pdfUrl) {
    app.appendChild(renderCard(`<p class="state-message success">✓ Your PDF is ready.</p>`, "animate-in"));

    const preview = document.createElement("iframe");
    preview.className = "pdf-preview animate-in";
    preview.src = state.pdfUrl;
    preview.title = "Generated PDF preview";
    app.appendChild(preview);

    const actions = document.createElement("div");
    actions.className = "pdf-actions animate-in";

    const backBtn = document.createElement("button");
    backBtn.type = "button";
    backBtn.className = "link-btn";
    backBtn.textContent = "← Edit selection";
    backBtn.addEventListener("click", () => {
      setStatus("ready-to-select");
      render();
    });

    const link = document.createElement("a");
    link.className = "btn btn-primary download-link";
    link.href = state.pdfUrl;
    link.download = "study-notes.pdf";
    link.textContent = "Download PDF";

    actions.append(backBtn, link);
    app.appendChild(actions);
  }
}

function renderCard(innerHtml, extraClass = "") {
  const card = document.createElement("div");
  card.className = `card ${extraClass}`.trim();
  card.innerHTML = innerHtml;
  return card;
}

/**
 * The empty state — shown when nothing is loaded yet (idle) and after a
 * failed attempt (error, with the message swapped in above the form so a
 * bad paste is easy to correct without starting over). Deliberately not
 * a boxed card with a numbered checklist: on a tall, narrow panel with
 * nothing else on screen, a centered icon + one confident heading + one
 * line of help text reads as a considered empty state rather than a
 * template stretched to fill the space.
 */
function renderEmptyState({ error, prefillUrl = "" } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "empty-state animate-in";

  const iconWrap = document.createElement("div");
  iconWrap.className = "empty-icon";
  iconWrap.setAttribute("aria-hidden", "true");
  iconWrap.innerHTML = error
    ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
         <path d="M12 9v4" /><path d="M12 17h.01" />
         <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
       </svg>`
    : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
         <path d="M12 3v12" /><path d="M7 10l5 5 5-5" /><path d="M5 21h14" />
       </svg>`;
  wrap.appendChild(iconWrap);

  const title = document.createElement("h2");
  title.className = "empty-title";
  title.textContent = error ? "Couldn't load that link" : "Paste a share link";
  wrap.appendChild(title);

  const copy = document.createElement("p");
  copy.className = "empty-copy";
  copy.innerHTML = error
    ? escapeHtml(error)
    : `Open the conversation on chatgpt.com, click <strong>Share</strong> to get a public link, then drop it in below.`;
  wrap.appendChild(copy);

  const form = document.createElement("form");
  form.className = "search-row";
  form.id = "manualUrlForm";
  form.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M10 13a5 5 0 0 0 7.07 0l1.41-1.41a5 5 0 0 0-7.07-7.07L10 6" />
      <path d="M14 11a5 5 0 0 0-7.07 0L5.5 12.4a5 5 0 0 0 7.07 7.07L14 18" />
    </svg>
  `;
  const input = document.createElement("input");
  input.type = "url";
  input.id = "manualUrlInput";
  input.className = "search-input";
  input.placeholder = "https://chatgpt.com/share/…";
  input.value = prefillUrl;
  form.appendChild(input);
  wrap.appendChild(form);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitManualUrl();
  });

  const loadBtn = document.createElement("button");
  loadBtn.type = "button";
  loadBtn.className = "btn btn-primary btn-block";
  loadBtn.textContent = "Load conversation";
  loadBtn.addEventListener("click", submitManualUrl);
  wrap.appendChild(loadBtn);

  return wrap;
}

function submitManualUrl() {
  const input = document.getElementById("manualUrlInput");
  if (!input) return;

  const url = input.value.trim();
  if (!isChatGptShareUrl(url)) {
    setStatus("error");
    state.error =
      'That doesn\'t look like a ChatGPT share link. Click "Share" on the conversation and paste the link that starts with chatgpt.com/share/ or chat.openai.com/share/.';
    render();
    return;
  }

  handleParse(url);
}

function renderSkeleton() {
  const card = document.createElement("div");
  card.className = "card animate-in";
  const rows = Array.from({ length: 5 })
    .map(
      (_, i) => `
      <div class="skeleton-row" style="animation-delay:${i * 40}ms">
        <div class="skeleton skeleton-checkbox"></div>
        <div class="skeleton skeleton-line" style="width:${85 - i * 8}%"></div>
      </div>`
    )
    .join("");
  card.innerHTML = `
    <div class="skeleton skeleton-title"></div>
    <div class="skeleton skeleton-line" style="width:40%;margin-bottom:14px;"></div>
    <div class="skeleton-list">${rows}</div>
  `;
  return card;
}

function getFilteredSections() {
  const query = state.filterQuery.trim().toLowerCase();
  const all = state.conversation.sections;
  if (!query) return all;
  return all.filter((section) => (section.question?.content || "").toLowerCase().includes(query));
}

function renderSectionPicker({ disabled = false } = {}) {
  const card = document.createElement("div");
  card.className = "card animate-in";

  const title = document.createElement("p");
  title.className = "section-title";
  title.textContent = state.conversation.title || "Untitled conversation";
  card.appendChild(title);

  const count = document.createElement("p");
  count.className = "selected-count";
  count.textContent = `${state.selectedIds.size} of ${state.conversation.sections.length} selected`;
  card.appendChild(count);

  // Raycast-style command bar: filters the list client-side only, purely
  // a UI convenience — it never changes what gets sent to the backend.
  const searchRow = document.createElement("div");
  searchRow.className = "search-row";
  searchRow.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  `;
  const searchInput = document.createElement("input");
  searchInput.type = "search";
  searchInput.id = "sectionSearch";
  searchInput.className = "search-input";
  searchInput.placeholder = "Search prompts…";
  searchInput.value = state.filterQuery;
  searchInput.disabled = disabled;
  searchInput.addEventListener("input", (event) => {
    state.filterQuery = event.target.value;
    const cursor = event.target.selectionStart;
    render();
    // Every render rebuilds the DOM from scratch, which would otherwise
    // steal focus out of this input on every keystroke — restore it
    // synchronously so typing feels uninterrupted.
    const freshInput = document.getElementById("sectionSearch");
    if (freshInput) {
      freshInput.focus();
      freshInput.setSelectionRange(cursor, cursor);
    }
  });
  searchRow.appendChild(searchInput);
  card.appendChild(searchRow);

  const actions = document.createElement("div");
  actions.className = "section-actions";

  const selectAllBtn = document.createElement("button");
  selectAllBtn.type = "button";
  selectAllBtn.className = "btn btn-secondary";
  selectAllBtn.textContent = "Select all";
  selectAllBtn.disabled = disabled;
  selectAllBtn.addEventListener("click", () => {
    state.selectedIds = new Set(state.conversation.sections.map((section) => section.id));
    render();
  });

  const deselectAllBtn = document.createElement("button");
  deselectAllBtn.type = "button";
  deselectAllBtn.className = "btn btn-secondary";
  deselectAllBtn.textContent = "Deselect all";
  deselectAllBtn.disabled = disabled;
  deselectAllBtn.addEventListener("click", () => {
    state.selectedIds = new Set();
    render();
  });

  actions.append(selectAllBtn, deselectAllBtn);
  card.appendChild(actions);

  const filtered = getFilteredSections();

  if (filtered.length === 0) {
    const empty = document.createElement("p");
    empty.className = "state-message";
    empty.textContent = "No prompts match your search.";
    card.appendChild(empty);
  } else {
    const list = document.createElement("ul");
    list.className = "section-list";
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-label", "Conversation sections");

    filtered.forEach((section, i) => {
      const item = document.createElement("li");
      item.className = "section-item animate-in";
      item.style.animationDelay = `${Math.min(i, 8) * 30}ms`;
      item.tabIndex = disabled ? -1 : 0;
      item.setAttribute("role", "option");

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = state.selectedIds.has(section.id);
      checkbox.disabled = disabled;
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.selectedIds.add(section.id);
        else state.selectedIds.delete(section.id);
        render();
      });

      const preview = document.createElement("span");
      preview.className = "question-preview";
      preview.textContent = section.question?.content || "(no question — conversation opener)";

      item.append(checkbox, preview);
      item.setAttribute("aria-selected", String(checkbox.checked));
      item.addEventListener("click", () => {
        if (disabled) return;
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event("change"));
      });

      list.appendChild(item);
    });

    // Roving keyboard navigation across rows — arrow keys move focus,
    // space/enter toggles, mirroring Raycast's list interaction model.
    list.addEventListener("keydown", (event) => {
      const items = Array.from(list.querySelectorAll(".section-item"));
      const currentIndex = items.indexOf(document.activeElement);

      if (event.key === "ArrowDown") {
        event.preventDefault();
        (items[currentIndex + 1] || items[0])?.focus();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        (items[currentIndex - 1] || items[items.length - 1])?.focus();
      } else if (event.key === " " || event.key === "Enter") {
        event.preventDefault();
        document.activeElement?.querySelector("input[type=checkbox]")?.click();
      }
    });

    card.appendChild(list);
  }

  const generateBtn = document.createElement("button");
  generateBtn.type = "button";
  generateBtn.className = "btn btn-primary btn-block";
  generateBtn.textContent = "Generate PDF";
  generateBtn.disabled = disabled || state.selectedIds.size === 0;
  generateBtn.addEventListener("click", handleGenerate);
  card.appendChild(generateBtn);

  return card;
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

async function handleParse(shareUrl) {
  state.shareUrl = shareUrl;
  state.filterQuery = "";
  state.error = null;
  setStatus("parsing");
  render();

  try {
    const conversation = await parseConversation(shareUrl);
    state.conversation = conversation;
    state.selectedIds = new Set(conversation.sections.map((section) => section.id));
    setStatus("ready-to-select");
  } catch (err) {
    setStatus("error");
    state.error = err instanceof ApiError ? err.message : "Something went wrong while parsing the conversation.";
  }
  render();
}

async function handleGenerate() {
  setStatus("generating");
  render();

  const selectedSections = state.conversation.sections.filter((section) => state.selectedIds.has(section.id));

  try {
    const blob = await generatePdf({
      title: state.conversation.title,
      source_url: state.conversation.source_url,
      selected_sections: selectedSections,
    });
    state.pdfUrl = URL.createObjectURL(blob);
    setStatus("pdf-ready");
  } catch (err) {
    setStatus("error");
    state.error = err instanceof ApiError ? err.message : "Something went wrong while generating the PDF.";
  }
  render();
}

/**
 * Returns to the paste-a-link screen without a full close/reopen of the
 * panel. `state.shareUrl` is deliberately left in place (not cleared) so
 * the empty-state form can prefill it — this is meant to be "go edit the
 * URL", not "start over from a blank field". It gets overwritten the
 * moment a new parse actually runs (see `handleParse`).
 */
function handleChangeUrl() {
  state.conversation = null;
  state.selectedIds = new Set();
  state.filterQuery = "";
  state.error = null;
  if (state.pdfUrl) {
    URL.revokeObjectURL(state.pdfUrl);
    state.pdfUrl = null;
  }
  setStatus("idle");
  render();
  document.getElementById("manualUrlInput")?.focus();
}

function focusSearchInput() {
  const input = document.getElementById("sectionSearch") ?? document.getElementById("manualUrlInput");
  input?.focus();
}

// ---------- Global keyboard shortcuts (Raycast/Arc conventions) ----------

document.addEventListener("keydown", (event) => {
  const meta = event.metaKey || event.ctrlKey;
  const activeTag = document.activeElement?.tagName;
  const isTypingField = activeTag === "INPUT" || activeTag === "TEXTAREA";

  if (meta && event.key.toLowerCase() === "k") {
    event.preventDefault();
    focusSearchInput();
    return;
  }

  if (event.key === "Escape") {
    if (isTypingField) {
      document.activeElement.blur();
      return;
    }
    // Chrome's docked side panel has no "close" affordance to trigger
    // here, but Safari's popup-window fallback (see background.js) can
    // be closed — Escape dismissing a floating panel is the Raycast/Arc
    // convention this mirrors.
    if (!browserAPI.sidePanel) window.close();
    return;
  }

  if (isTypingField) return;
  if (state.status !== "ready-to-select") return;

  if (meta && event.key.toLowerCase() === "a") {
    event.preventDefault();
    state.selectedIds = new Set(state.conversation.sections.map((section) => section.id));
    render();
    return;
  }

  if (meta && (event.key === "Backspace" || event.key.toLowerCase() === "d")) {
    event.preventDefault();
    state.selectedIds = new Set();
    render();
    return;
  }

  if (meta && event.key === "Enter" && state.selectedIds.size > 0) {
    event.preventDefault();
    handleGenerate();
  }
});

// --- Wiring: read the share URL the content script stored via the
// background service worker, and react live if a new "Export" click
// comes in while the panel is already open. ---

initTheme();
setStatus("idle");
render();
playEntranceAnimation();

browserAPI.storage.local.get("shareUrl").then(({ shareUrl }) => {
  if (shareUrl) handleParse(shareUrl);
});

browserAPI.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local" || !changes.shareUrl) return;
  const newUrl = changes.shareUrl.newValue;
  if (newUrl && newUrl !== state.shareUrl) handleParse(newUrl);
});
