/**
 * Thin fetch wrapper shared by all API service modules.
 * Centralizing this makes it trivial to add auth headers, retries, or
 * request/response logging later without touching every call site.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new ApiError(detail?.detail || response.statusText, response.status);
  }

  return response;
}
