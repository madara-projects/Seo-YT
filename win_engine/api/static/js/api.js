import { FrontendApiError } from "./errors.js";

/**
 * Shared same-origin API client for the extracted frontend.
 *
 * All requests intentionally flow through this module so normalized backend
 * errors, request IDs, safe JSON parsing, and mutation semantics stay in one
 * place during the Phase 3C extraction.
 */
export async function apiRequest(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (_) {
    throw new FrontendApiError("Network request failed. Check that the local server is running.");
  }

  let data = {};
  const raw = await response.text();
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch (_) {
      data = { raw };
    }
  }
  if (!response.ok) {
    const envelope = data && data.error && typeof data.error === "object" ? data.error : {};
    throw new FrontendApiError(
      envelope.message || data.detail || data.message || `Request failed (${response.status}).`,
      envelope.request_id || data.request_id || "",
      response.status,
    );
  }
  return data;
}
