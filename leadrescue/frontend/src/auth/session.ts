/**
 * Staff sessions.
 * - demo: local server issues a short-lived signed token for a demo staff profile (no password; clearly labeled).
 * - cognito: Cognito Hosted UI, authorization code flow with PKCE. Tokens are kept in sessionStorage
 *   (cleared when the tab closes). No refresh tokens are stored; staff sign in again when the access token expires.
 */
import { apiRequest } from "../api/client";

export type AuthMode = "demo" | "cognito";
export const AUTH_MODE: AuthMode = import.meta.env.VITE_AUTH_MODE === "cognito" ? "cognito" : "demo";

export interface Session {
  token: string;
  expiresAt: number; // epoch seconds
  user: { id: string; name: string };
  mode: AuthMode;
}

const KEY = "leadrescue.session";
const PKCE_KEY = "leadrescue.pkce";

function safeStorage(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function loadSession(): Session | null {
  const raw = safeStorage()?.getItem(KEY);
  if (!raw) return null;
  try {
    const s = JSON.parse(raw) as Session;
    if (!s.token || s.expiresAt * 1000 <= Date.now()) {
      clearSession();
      return null;
    }
    return s;
  } catch {
    clearSession();
    return null;
  }
}

export function saveSession(s: Session) {
  safeStorage()?.setItem(KEY, JSON.stringify(s));
}

export function clearSession() {
  safeStorage()?.removeItem(KEY);
}

export async function demoSignIn(staffId: string): Promise<Session> {
  const res = await apiRequest<{ token: string; expiresAt: number; user: { id: string; name: string } }>("POST", "/api/demo/session", {
    body: { staffId },
    auth: false,
  });
  const s: Session = { token: res.token, expiresAt: res.expiresAt, user: res.user, mode: "demo" };
  saveSession(s);
  return s;
}

// ---- Cognito Hosted UI (PKCE) ----------------------------------------------
const cognito = {
  domain: (import.meta.env.VITE_COGNITO_DOMAIN ?? "").replace(/\/$/, ""),
  clientId: import.meta.env.VITE_COGNITO_CLIENT_ID ?? "",
  redirectUri: import.meta.env.VITE_COGNITO_REDIRECT_URI ?? `${window.location.origin}/auth/callback`,
  logoutUri: import.meta.env.VITE_COGNITO_LOGOUT_URI ?? `${window.location.origin}/signin`,
};

export function cognitoConfigured(): boolean {
  return Boolean(cognito.domain && cognito.clientId);
}

function b64url(bytes: ArrayBuffer | Uint8Array): string {
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let s = "";
  arr.forEach((b) => (s += String.fromCharCode(b)));
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function startCognitoSignIn(returnTo: string) {
  const verifier = b64url(crypto.getRandomValues(new Uint8Array(32)));
  const state = b64url(crypto.getRandomValues(new Uint8Array(16)));
  const challenge = b64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
  safeStorage()?.setItem(PKCE_KEY, JSON.stringify({ verifier, state, returnTo }));
  const params = new URLSearchParams({
    response_type: "code",
    client_id: cognito.clientId,
    redirect_uri: cognito.redirectUri,
    scope: "openid email profile",
    code_challenge_method: "S256",
    code_challenge: challenge,
    state,
  });
  window.location.assign(`${cognito.domain}/oauth2/authorize?${params}`);
}

function decodeJwtPayload(token: string): Record<string, unknown> {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(decodeURIComponent(escape(atob(part))));
  } catch {
    return {};
  }
}

export async function completeCognitoSignIn(search: string): Promise<{ session: Session; returnTo: string }> {
  const params = new URLSearchParams(search);
  const stored = JSON.parse(safeStorage()?.getItem(PKCE_KEY) ?? "null") as { verifier: string; state: string; returnTo: string } | null;
  safeStorage()?.removeItem(PKCE_KEY);
  if (params.get("error")) throw new Error(params.get("error_description") ?? "Sign-in was cancelled.");
  const code = params.get("code");
  if (!code || !stored || params.get("state") !== stored.state) throw new Error("Sign-in could not be verified. Please try again.");
  const res = await fetch(`${cognito.domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: cognito.clientId,
      code,
      redirect_uri: cognito.redirectUri,
      code_verifier: stored.verifier,
    }),
  });
  if (!res.ok) throw new Error("Sign-in failed while exchanging the authorization code.");
  const tokens = (await res.json()) as { access_token: string; id_token: string; expires_in: number };
  const idClaims = decodeJwtPayload(tokens.id_token);
  const session: Session = {
    token: tokens.access_token,
    expiresAt: Math.floor(Date.now() / 1000) + tokens.expires_in,
    user: { id: String(idClaims.sub ?? ""), name: String(idClaims.name ?? idClaims.email ?? idClaims["cognito:username"] ?? "Staff") },
    mode: "cognito",
  };
  saveSession(session);
  return { session, returnTo: stored.returnTo || "/" };
}

export function cognitoLogoutUrl(): string {
  const params = new URLSearchParams({ client_id: cognito.clientId, logout_uri: cognito.logoutUri });
  return `${cognito.domain}/logout?${params}`;
}
