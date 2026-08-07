/**
 * Central config for the extension. Shared as-is by both platform builds.
 *
 * Update BACKEND_BASE_URL once the FastAPI backend is deployed somewhere
 * public — for local development it just points at the same
 * `localhost:8000` server the web app itself talks to (see
 * `/backend/.env.example` and `/frontend/.env.example`). The extension
 * calls the exact same `/api/parse` and `/api/generate-pdf` endpoints the
 * web app uses; no parser or PDF logic is duplicated anywhere here.
 */
export const BACKEND_BASE_URL = "http://localhost:8000/api";
