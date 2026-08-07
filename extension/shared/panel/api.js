/**
 * Thin fetch wrappers around the existing backend — the same two
 * endpoints (`POST /api/parse`, `POST /api/generate-pdf`) the main web
 * app already calls. This file intentionally mirrors
 * `frontend/src/services/api/client.js` / `conversationApi.js` /
 * `pdfApi.js` in shape: it's the unavoidable bit of glue every HTTP
 * client needs, not a reimplementation of any parsing or PDF logic —
 * that all still lives exactly once, server-side, in `backend/app/`.
 *
 * Plain `fetch`, no browser-extension APIs — shared as-is between the
 * Chrome and Safari builds.
 */
import { BACKEND_BASE_URL } from "../config.js";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${BACKEND_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
  } catch {
    throw new ApiError("Could not reach the ChatBook backend. Is it running?", 0);
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new ApiError(detail?.detail || response.statusText, response.status);
  }

  return response;
}

/**
 * @param {string} url
 * @returns {Promise<object>} the same ParseConversationResponse shape the web app uses.
 */
export async function parseConversation(url) {
  const response = await apiRequest("/parse", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
  return response.json();
}

/**
 * @param {{title: string, source_url?: string, selected_sections: object[]}} payload
 * @returns {Promise<Blob>}
 */
export async function generatePdf(payload) {
  const response = await apiRequest("/generate-pdf", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return response.blob();
}
