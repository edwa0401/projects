import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest, ApiError, configureClient } from "../../src/api/client";
import { clearSession, loadSession, saveSession } from "../../src/auth/session";
import { draftPolicyWarnings } from "../../src/lib/labels";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue(new Response(body === undefined ? "" : JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearSession();
});

describe("apiRequest", () => {
  it("sends the bearer token and idempotency key", async () => {
    configureClient(() => "tok-123", () => {});
    const fetchFn = mockFetch(200, { ok: true });
    await apiRequest("POST", "/api/inquiries", { body: { message: "hi" }, idempotencyKey: "key-abcdef12" });
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe("/api/inquiries");
    expect(init.headers.Authorization).toBe("Bearer tok-123");
    expect(init.headers["Idempotency-Key"]).toBe("key-abcdef12");
    expect(JSON.parse(init.body)).toEqual({ message: "hi" });
  });

  it("reports 401 as session expiry", async () => {
    const onUnauthorized = vi.fn();
    configureClient(() => "tok", onUnauthorized);
    mockFetch(401, { error: { code: "session_expired", message: "Your session expired. Sign in again." } });
    await expect(apiRequest("GET", "/api/inquiries")).rejects.toMatchObject({ status: 401, code: "session_expired" });
    expect(onUnauthorized).toHaveBeenCalledWith("session_expired");
  });

  it("does not call the API without a token", async () => {
    const onUnauthorized = vi.fn();
    configureClient(() => null, onUnauthorized);
    const fetchFn = mockFetch(200, {});
    await expect(apiRequest("GET", "/api/inquiries")).rejects.toBeInstanceOf(ApiError);
    expect(fetchFn).not.toHaveBeenCalled();
    expect(onUnauthorized).toHaveBeenCalled();
  });

  it("turns network failures into a friendly error", async () => {
    configureClient(() => "tok", () => {});
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(apiRequest("GET", "/api/inquiries")).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("surfaces validation details", async () => {
    configureClient(() => "tok", () => {});
    mockFetch(400, { error: { code: "validation_error", message: "Please fix", details: { fields: { message: "Required" } } } });
    await expect(apiRequest("POST", "/api/inquiries", { body: {} })).rejects.toMatchObject({ details: { fields: { message: "Required" } } });
  });
});

describe("session storage", () => {
  it("drops expired sessions", () => {
    saveSession({ token: "t", expiresAt: Math.floor(Date.now() / 1000) - 5, user: { id: "u", name: "U" }, mode: "demo" });
    expect(loadSession()).toBeNull();
  });
  it("keeps valid sessions", () => {
    saveSession({ token: "t", expiresAt: Math.floor(Date.now() / 1000) + 600, user: { id: "u", name: "U" }, mode: "demo" });
    expect(loadSession()?.token).toBe("t");
  });
});

describe("draft policy mirror", () => {
  it.each([
    ["Thanks! A team member will follow up with an estimate.", 0],
    ["Your move is confirmed for Monday.", 1],
    ["The total will be $850.", 1],
    ["Good news, this is a free move!", 1],
    ["Your current booking is not confirmed until our scheduler calls you.", 0],
  ])("%s", (text, count) => {
    expect(draftPolicyWarnings(text).length > 0).toBe(count > 0);
  });
});
