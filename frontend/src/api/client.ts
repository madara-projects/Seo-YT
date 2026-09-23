/**
 * Same-origin API client.
 *
 * Mirrors the contract the legacy `static/js/api.js` established: the backend
 * returns `{ error: { code, message, request_id } }` on failure, and the
 * request ID must survive all the way to the surface so a user can quote it
 * from a log line. Everything goes through here so that stays in one place.
 */

export class ApiError extends Error {
  readonly requestId: string;
  readonly status: number;
  readonly code: string;

  constructor(message: string, requestId = "", status = 0, code = "") {
    super(message);
    this.name = "ApiError";
    this.requestId = requestId;
    this.status = status;
    this.code = code;
  }
}

/**
 * The bare human-readable message, with no request ID appended.
 *
 * Use this anywhere the request ID is displayed separately — `ErrorState`
 * renders it as its own line — otherwise it appears twice.
 */
export function apiErrorMessage(error: unknown, fallback = "Request failed."): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

/**
 * Message plus request ID as one string, for surfaces with nowhere else to put
 * it — toasts, single-line alerts.
 */
export function formatApiError(error: unknown, fallback = "Request failed."): string {
  const message = apiErrorMessage(error, fallback);
  if (error instanceof ApiError && error.requestId) {
    return `${message} Request ID: ${error.requestId}`;
  }
  return message;
}

/** The request ID when the failure carried one, for separate display. */
export function apiRequestId(error: unknown): string {
  return error instanceof ApiError ? error.requestId : "";
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  /** Overrides the default absence of a client timeout. */
  timeoutMs?: number;
};

export async function apiRequest<T = unknown>(
  url: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, timeoutMs, headers, signal, ...rest } = options;

  const controller = new AbortController();
  const timer =
    typeof timeoutMs === "number" && timeoutMs > 0
      ? window.setTimeout(() => controller.abort(), timeoutMs)
      : undefined;

  // Caller-supplied cancellation still wins.
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...rest,
      signal: controller.signal,
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(headers ?? {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (cause) {
    if (controller.signal.aborted) {
      throw new ApiError("The request was cancelled before the server replied.", "", 0, "aborted");
    }
    throw new ApiError(
      "Network request failed. Check that the local server is running.",
      "",
      0,
      "network_error",
    );
  } finally {
    if (timer !== undefined) window.clearTimeout(timer);
  }

  const raw = await response.text();
  let data: Record<string, unknown> = {};
  if (raw) {
    try {
      data = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      data = { raw };
    }
  }

  if (!response.ok) {
    const envelope =
      data.error && typeof data.error === "object" ? (data.error as Record<string, unknown>) : {};
    throw new ApiError(
      String(
        envelope.message ?? data.detail ?? data.message ?? `Request failed (${response.status}).`,
      ),
      String(envelope.request_id ?? data.request_id ?? ""),
      response.status,
      String(envelope.code ?? ""),
    );
  }

  return data as T;
}
