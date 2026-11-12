/** Fetch wrapper: attaches the staff token, normalizes errors, and reports 401s as session expiry. */

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type TokenProvider = () => string | null;
type UnauthorizedHandler = (code: string) => void;

let getToken: TokenProvider = () => null;
let onUnauthorized: UnauthorizedHandler = () => {};

export function configureClient(tokenProvider: TokenProvider, unauthorized: UnauthorizedHandler) {
  getToken = tokenProvider;
  onUnauthorized = unauthorized;
}

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `k${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
}

export interface RequestOptions {
  body?: unknown;
  idempotencyKey?: string;
  query?: Record<string, string | undefined>;
  auth?: boolean;
}

export async function apiRequest<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.idempotencyKey) headers["Idempotency-Key"] = opts.idempotencyKey;
  if (opts.auth !== false) {
    const token = getToken();
    if (!token) {
      onUnauthorized("session_expired");
      throw new ApiError(401, "session_expired", "Your session expired. Sign in again.");
    }
    headers.Authorization = `Bearer ${token}`;
  }
  let url = `${API_BASE}${path}`;
  if (opts.query) {
    const qs = new URLSearchParams();
    Object.entries(opts.query).forEach(([k, v]) => v && qs.set(k, v));
    const s = qs.toString();
    if (s) url += `?${s}`;
  }
  let res: Response;
  try {
    res = await fetch(url, { method, headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the LeadRescue API. Check your connection and try again. Nothing was lost.");
  }
  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!res.ok) {
    const err = (payload as { error?: { code?: string; message?: string; details?: unknown }; message?: string } | null) ?? {};
    const code = err.error?.code ?? (res.status === 401 ? "unauthorized" : "http_error");
    const message =
      err.error?.message ?? err.message ?? (res.status === 401 ? "Your session expired. Sign in again." : `Request failed (${res.status}).`);
    if (res.status === 401) onUnauthorized(code);
    throw new ApiError(res.status, code, message, err.error?.details);
  }
  return payload as T;
}
