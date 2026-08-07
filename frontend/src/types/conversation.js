/**
 * Shared type definitions (JSDoc) mirroring the backend Pydantic schemas
 * in `backend/app/schemas/conversation.py`. This project uses plain JS
 * rather than TypeScript, so JSDoc typedefs give editor-level type
 * checking (see jsconfig.json `checkJs`) without a build step.
 */

/**
 * @typedef {Object} MessageDTO
 * @property {string} id
 * @property {"user"|"assistant"} role
 * @property {string} content
 * @property {number} order
 */

/**
 * @typedef {Object} QaSectionDTO
 * @property {string} id
 * @property {number} section_index
 * @property {?MessageDTO} question - null if the conversation started with
 *   an assistant message before any user turn (rare).
 * @property {?MessageDTO} answer - null if this question hasn't been
 *   answered yet (e.g. the conversation ends on a user message).
 */

/**
 * @typedef {Object} ParseConversationResponse
 * @property {string} title
 * @property {string} source_url
 * @property {MessageDTO[]} messages - the complete, ordered list of every
 *   extracted user/assistant message (authoritative source of truth).
 * @property {QaSectionDTO[]} sections - the same messages, paired into Q&A
 *   sections for the section-picker UI.
 */

export {};
