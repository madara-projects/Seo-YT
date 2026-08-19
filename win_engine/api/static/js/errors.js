/** Normalized frontend error contract shared by every page. */
export class FrontendApiError extends Error {
  constructor(message, requestId = "", status = 0) {
    super(message);
    this.name = "FrontendApiError";
    this.requestId = requestId || "";
    this.status = status || 0;
  }
}

export function formatApiError(error, fallback = "Request failed.") {
  const message = error && error.message ? error.message : fallback;
  const requestId = error && error.requestId ? ` Request ID: ${error.requestId}` : "";
  return message + requestId;
}

export function renderApiError(element, error, fallback) {
  if (!element) return;
  element.textContent = formatApiError(error, fallback);
  element.style.color = "var(--bad)";
}
