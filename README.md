# ChatBook

Turns a ChatGPT shared conversation into structured study notes and a
textbook-styled PDF — not a chat screenshot.

The ChatGPT share-page parser/fetcher and the PDF generation pipeline are
both fully implemented — see "Parser implementation" and "PDF generation"
below.

## Flow

```
User pastes ChatGPT shared link
        v
Backend fetches conversation      (ChatFetcher)
        v
Parser converts to structured JSON (ConversationParser)
        v
Frontend displays every Q&A section (Conversation Preview page)
        v
User selects sections
        v
Backend renders sections to HTML   (HtmlDocumentBuilder: Markdown,
                                    syntax highlighting, LaTeX)
        v
Backend rasterizes HTML to PDF     (PDFGenerator + WeasyPrint)
        v
Frontend downloads the PDF
```

## Tech stack

Frontend: React, JavaScript (JSDoc for types, see note below), Tailwind
CSS, shadcn/ui-style components, TanStack Query, Zustand.

Backend: Python, FastAPI, Pydantic, httpx, BeautifulSoup, Jinja2 +
python-Markdown + Pygments for HTML rendering, Matplotlib (`mathtext`)
for LaTeX-to-image rendering, and WeasyPrint for HTML-to-PDF
rasterization.

Database: none yet. The app is stateless — conversations and selections
live in frontend memory (Zustand) for the duration of a session. Postgres
+ Supabase is a planned addition (see "Future features" below).

### Why JS + JSDoc instead of TypeScript

The spec calls for JS on the frontend but "strong typing everywhere."
JSDoc typedefs (`frontend/src/types/*.js`) plus `jsconfig.json`
(`checkJs: true`) give editor-level type checking and autocomplete without
introducing a TS build step. The typedefs are written to mirror the
backend's Pydantic schemas field-for-field, so the two stay in sync
manually until/unless the project moves to TypeScript or codegen.

## Backend structure

```
backend/
  app/
    main.py                    FastAPI app, CORS, router mounting, /health
    config/settings.py         Env-driven Settings (pydantic-settings)
    api/
      deps.py                  DI providers for services
      routes/
        parse.py               POST /api/parse
        pdf.py                 POST /api/generate-pdf
    schemas/                   API request/response DTOs (Pydantic)
      conversation.py
      pdf.py
    models/                    Internal domain models (dataclasses)
      conversation.py          Message, QaSection, Conversation
    services/                  Business logic, orchestration
      chat_fetcher.py          ChatFetcher — retrieves raw HTML only
      conversation_service.py  ConversationService — fetch + parse use case
      pdf_service.py           PdfService — wraps PDFGenerator
    parsers/                   HTML/JSON -> domain model (see below)
      base.py                  BaseConversationParser interface
      conversation_parser.py   ConversationParser — thin orchestrator
      loader_extraction.py     Pulls embedded JSON out of <script> tags
      payload_locator.py       Finds the conversation dict within that JSON
      conversation_builder.py  Builds ordered Messages + QaSections
      message_content.py       One message's content -> Markdown
    pdf/                       Sections -> HTML -> PDF bytes (two decoupled layers)
      html_renderer.py         HtmlDocumentBuilder — sections -> one HTML string
      generator.py             PDFGenerator — HTML string -> PDF bytes (only file
                                that imports WeasyPrint)
      markdown_renderer.py     MarkdownRenderer (python-Markdown + codehilite)
      syntax_highlighting.py   Pygments CSS for highlighted code blocks
      latex_renderer.py        LatexRenderer (Matplotlib mathtext -> SVG images)
      templates/base_template.html   Cover page, TOC, numbered content pages
    utils/
      exceptions.py            Typed AppError hierarchy
      logger.py                Shared logger factory
  tests/
    test_health.py
    parsers/                   Unit + end-to-end tests for the parser pipeline
    services/                  ChatFetcher validation/error-mapping tests
    pdf/                       Unit tests for the HTML/PDF generation pipeline
  requirements.txt
  .env.example
```

## Parser implementation

`ConversationParser.parse(raw_html, source_url)` turns a fetched share page
into a `Conversation` (title + ordered `messages` + paired `sections`).
Everything that knows about ChatGPT's actual HTML/JSON structure lives
inside `app/parsers/`, so a future OpenAI markup change only requires
editing that package:

1. **`loader_extraction.py`** finds the embedded conversation JSON. Modern
   `chatgpt.com` share pages stream it via a
   `window.__reactRouterContext.streamController.enqueue(...)` call in a
   `<script>` tag (a flattened, index-deduplicated array — the same trick
   used by React Flight/RSC payloads); legacy `chat.openai.com` pages use a
   `<script id="__NEXT_DATA__">` tag with plain JSON. Both are supported.
2. **`payload_locator.py`** finds the actual conversation dict (a `mapping`
   of node id -> message) within that JSON — first via the known route/key
   path, then via a structural fallback search (looks for a dict shaped
   like a conversation) so a route rename alone doesn't break parsing.
3. **`conversation_builder.py`** orders the message nodes (via
   `linear_conversation` if present, else by walking `parent` links from
   `current_node`), filters out system/tool/hidden-reasoning messages, and
   pairs adjacent user/assistant runs into `QaSection`s.
4. **`message_content.py`** converts each message's raw `content` dict into
   a Markdown string. Text messages already store the model's raw Markdown
   source (fenced code blocks, lists, pipe tables, LaTeX like `$$...$$` or
   `\(...\)` are just characters in that string), so extracting `parts`
   verbatim — never rendering through HTML — is what preserves all of it
   losslessly.

`ChatFetcher` validates the URL (must be `https://chatgpt.com/share/<id>`
or the legacy `chat.openai.com` equivalent — private `/c/...` links are
rejected before any request is made) and maps fetch failures to specific
messages (404 = deleted/invalid link, 403/401 = private conversation).

Design notes:

- Routes never contain business logic. `api/routes/*.py` only validates
  input, calls a service, and maps the result to a response schema.
- `schemas/` (wire format) and `models/` (internal domain objects) are
  kept separate on purpose, so the API contract and internal processing
  can evolve independently.
- `ChatFetcher`, `ConversationParser`, `HtmlDocumentBuilder`,
  `PDFGenerator`, `MarkdownRenderer`, and `LatexRenderer` are each
  single-responsibility classes injected into the services/classes that
  use them (constructor injection), which makes them easy to swap or mock
  in tests.

## PDF generation

`PdfService.generate(title, sections, source_url)` turns the selected
`QaSection`s into PDF bytes in two decoupled steps, split across two
classes specifically so the document's look can be reworked without
touching PDF-conversion code at all:

1. **`HtmlDocumentBuilder`** (`app/pdf/html_renderer.py`) builds one
   self-contained HTML string: cover page (title, chapter count,
   generated date, optional source URL), a table of contents, and each
   Q&A pair rendered as its own numbered chapter. Sections are renumbered
   sequentially (1..N by list position) rather than reusing each
   section's original `section_index`, so deselecting sections in the
   preview never leaves gaps in the generated document. This is the only
   class that knows about the document's structure, and its Jinja2
   template (`templates/base_template.html`) is swappable via a
   constructor argument.
2. **`PDFGenerator`** (`app/pdf/generator.py`) takes that finished HTML
   string and rasterizes it with WeasyPrint. It's the only module in the
   codebase that imports `weasyprint`, and its `render_html_to_pdf`
   staticmethod works on any HTML string, not just ones
   `HtmlDocumentBuilder` produced.

Within `HtmlDocumentBuilder`, each message's Markdown is converted in
four passes so Markdown, LaTeX, syntax highlighting, and callouts don't
interfere with each other:

- **`LatexRenderer.extract()`** pulls every `$$...$$` / `\[...\]` /
  `\(...\)` / `$...$` segment out of the *raw* Markdown first (before
  Markdown can mangle the backslashes/underscores inside them), leaving
  opaque placeholders behind. Segments inside fenced or inline code spans
  are left untouched (so shell syntax like `` $HOME `` is never mistaken
  for math), and bare `$5`/`$10`-style currency doesn't match the pattern
  either. Each extracted segment is rendered to a standalone SVG via
  Matplotlib's `mathtext` engine and base64-embedded as a data URI: if
  mathtext can't parse it (e.g. a `\begin{bmatrix}` environment, which
  it doesn't support), it falls back to plainly-styled raw LaTeX source
  instead of dropping the content.
- **`MarkdownRenderer`** (python-Markdown with `extra` + `codehilite` +
  `sane_lists` + `nl2br`) converts the placeholder-substituted text to
  HTML; `codehilite` wraps fenced code blocks with Pygments-generated
  syntax-highlighting spans.
- **`LatexRenderer.restore()`** splices the rendered LaTeX images back
  into the resulting HTML in place of their placeholders.
- **`_apply_callout_styling()`** (BeautifulSoup) turns every Markdown
  blockquote into a highlighted callout box. If its leading word is
  "Note", "Tip", "Warning", "Caution", or "Important", that word is
  promoted into a small colored label and stripped from the body text
  (so it isn't shown twice); anything else falls back to a neutral,
  quote-style box. This is the one step that isn't a pure string
  substitution — it parses the fragment as HTML because detecting "does
  this blockquote start with a recognized keyword" isn't expressible as
  a regex once Markdown has already turned it into nested tags.

### Book-style design

The template (`base_template.html`) is deliberately built to read like a
printed technical book rather than an exported chat log: no
"Question"/"Answer" labels — each Q&A pair is a numbered **chapter**
(chapter kicker + title on its own page), the original question renders
as an italic "Topic" epigraph above the answer's prose rather than a
second chat bubble, and body text uses a serif typeface (Georgia) with
sans-serif headings, mirroring how most technical books pair the two.

It also uses CSS Paged Media / GCPM features WeasyPrint supports
natively:

- Named `@page` rules keep the cover and TOC unnumbered while content
  pages restart numbering at 1 and show "Page N of M" in the footer.
- Left/right margins mirror like a printed book (a wider inner margin, a
  narrower outer one) via the `:left`/`:right` page pseudo-classes.
- Running headers alternate book-style: verso (left) pages show the
  document title, recto (right) pages show the current chapter title,
  each pulled from a `string-set` on the corresponding heading.
- `target-counter(attr(href), page)` resolves each TOC entry to its real
  page number without JavaScript.

Pygments' CSS is generated once per document
(`syntax_highlighting.get_pygments_css()`) and embedded directly in the
`<style>` block, so the PDF never depends on external stylesheets or
fonts — every font referenced is a widely-available system font (Georgia
/ Helvetica Neue / a standard monospace stack), so rendering never
depends on a network fetch at generation time either.

## Frontend structure

```
frontend/
  src/
    app/            Route table + global providers
    components/
      layout/       Header, page chrome
      ui/           shadcn/ui-style primitives (Button, Checkbox, Card)
    features/       One folder per page/feature, each owning its
                    page component and any feature-local components
      home/                        URL input -> triggers /parse
      conversation-preview/        Section list + selection
      pdf-generation/              Loading state + download
    hooks/          TanStack Query mutation hooks (useParseConversation,
                    useGeneratePdf)
    services/api/   Fetch wrappers per resource (client.js is the shared
                    base; conversationApi.js / pdfApi.js call it)
    store/          Zustand store for cross-page state (selected
                    conversation + section selection)
    types/          JSDoc typedefs mirroring backend schemas
    lib/            cn() helper, QueryClient instance
    utils/          Route constants, text formatting helpers
```

Design notes:

- Pages are thin: they wire hooks + store + presentational components
  together, no fetch calls inline.
- Selection state (which sections are checked) lives in the Zustand store
  so it survives navigation between Preview and Generate without prop
  drilling.

## Running locally

Backend:
```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Frontend:
```
cd frontend
npm install
cp .env.example .env
npm run dev
```

## API endpoints

`POST /api/parse`
```json
// request
{ "url": "https://chatgpt.com/share/..." }

// response
{ "title": "...", "source_url": "...",
  "messages": [
    { "id": "...", "role": "user", "content": "...", "order": 0 },
    { "id": "...", "role": "assistant", "content": "...", "order": 1 }
  ],
  "sections": [
    { "id": "...", "section_index": 0,
      "question": { "id": "...", "role": "user", "content": "...", "order": 0 },
      "answer":   { "id": "...", "role": "assistant", "content": "...", "order": 1 } }
  ]
}
```
`messages` is the complete, ordered extraction (the source of truth);
`sections` is the same messages paired into Q&A turns for the
section-picker UI. `question`/`answer` can be `null` — a conversation can
end on an unanswered question, or (rarely) start with an assistant message
before any user turn.

`POST /api/generate-pdf`
```json
// request
{ "title": "optional override",
  "source_url": "https://chatgpt.com/share/... (optional, shown on cover page)",
  "selected_sections": [ /* QaSectionDTO[] */ ] }

// response: application/pdf (streamed, Content-Disposition: attachment)
```

## Extension points for planned features

The structure was chosen so these can be added without restructuring:

- AI summaries / flashcards / interview questions / quizzes: new modules
  under `backend/app/services/` (e.g. `summary_service.py`) that consume
  the same `Conversation` domain model, plus new frontend features under
  `frontend/src/features/`.
- EPUB export: a new renderer alongside `pdf/generator.py` (e.g.
  `epub/generator.py`) that reuses `HtmlDocumentBuilder`'s HTML output
  (or `MarkdownRenderer` directly) and the same `Conversation` model.
- Notion export / Chrome Extension: new modules under `services/`
  (e.g. `notion_export_service.py`) and a new `api/routes/` file; the
  Chrome Extension would call the existing `/api/parse` and
  `/api/generate-pdf` endpoints directly.
- Auth / saved documents / team sharing: introduces the planned
  PostgreSQL + Supabase layer. Add `db/` (models + session) and a
  `documents_service.py`; existing services stay unchanged since they
  don't currently touch persistence.
- Multi-chat merging: extend `ConversationService` with a
  `merge_conversations(urls: list[str])` method that fetches/parses each
  URL and concatenates `sections`, reusing everything already in place.

## Coding standards

Strong typing (Pydantic on the backend, JSDoc + `checkJs` on the
frontend), dependency injection via constructor params + FastAPI's
`Depends`, single-responsibility services, no business logic in routes
or page components, and typed exceptions (`AppError` subclasses) instead
of bare `Exception`/`HTTPException` raised deep in the call stack.
