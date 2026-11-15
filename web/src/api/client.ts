import createClient from "openapi-fetch";
import type { paths } from "./schema";

/**
 * The typed client. Paths, parameters and response bodies come from the generated schema, so a change
 * to the API shows up here as a compile error instead of a runtime surprise.
 *
 * Every request carries x-rb-client: the server refuses state-changing requests without it, which
 * stops another website from driving this local app through a form post.
 */
export const api = createClient<paths>({
  baseUrl: typeof location === "undefined" ? "http://localhost" : location.origin,
  headers: { "x-rb-client": "web" },
  // Look fetch up on every call. The client would otherwise keep the function that existed when this module loaded,
  // which hides any later replacement (a test double, an instrumented fetch) from it.
  fetch: (request) => globalThis.fetch(request),
});

export type ApiErrorCode =
  | "valkyrie_auth"
  | "valkyrie_network"
  | "valkyrie_rejected"
  | "valkyrie_error"
  | "read_only"
  | "forbidden"
  | "not_found"
  | "validation_error"
  | "conflict"
  | "confirmation_required"
  | "has_problems"
  | "database_unavailable"
  | "bad_gateway"
  | "internal"
  | "network"
  | "unknown";

/** What every failed call throws. ``code`` is the server's error code (or "network" when it never answered). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode;
  readonly detail: unknown;

  constructor(status: number, code: ApiErrorCode, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }

  /** True for failures worth retrying automatically (the server or Valkyrie hiccuped, not the request). */
  get transient(): boolean {
    return this.code === "network" || this.status >= 500;
  }
}

interface Envelope {
  error?: { code?: string; message?: string; detail?: unknown };
}

type Result<T> = { data?: T; error?: unknown; response: Response };

function toApiError(result: { error?: unknown; response: Response }): ApiError {
  const body = (result.error ?? {}) as Envelope;
  const status = result.response.status;
  const code = (body.error?.code ?? "unknown") as ApiErrorCode;
  const message = body.error?.message ?? (result.response.statusText || `Request failed (${status})`);
  return new ApiError(status, code, message, body.error?.detail);
}

/** Await a client call and return its data; throw an ApiError for anything that is not a success. */
export async function unwrap<T>(request: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await request;
  } catch (cause) {
    if (cause instanceof ApiError) throw cause;
    throw new ApiError(0, "network", "Cannot reach the RoyaleBench server. Is `python -m rb_server` running?", cause);
  }
  if (result.error !== undefined || !result.response.ok) throw toApiError(result);
  return result.data as T;
}

/** Field-level problems from a validation_error, keyed by field name ("" for form-level ones). */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || !Array.isArray(error.detail)) return {};
  const out: Record<string, string> = {};
  for (const item of error.detail as { field?: string; message?: string }[]) {
    if (item && typeof item.message === "string") out[item.field ?? ""] = item.message;
  }
  return out;
}
