import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { configureClient } from "../api/client";
import { AUTH_MODE, clearSession, cognitoLogoutUrl, loadSession, type Session } from "./session";

interface AuthState {
  session: Session | null;
  signOutReason: "expired" | "signed_out" | null;
  setSession: (s: Session) => void;
  signOut: (reason?: "expired" | "signed_out") => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(() => loadSession());
  const [signOutReason, setReason] = useState<"expired" | "signed_out" | null>(null);
  const sessionRef = useRef(session);
  sessionRef.current = session;

  const signOut = useCallback((reason: "expired" | "signed_out" = "signed_out") => {
    const wasCognito = sessionRef.current?.mode === "cognito";
    clearSession();
    setSessionState(null);
    setReason(reason);
    if (reason === "signed_out" && wasCognito && AUTH_MODE === "cognito") {
      window.location.assign(cognitoLogoutUrl());
    }
  }, []);

  const setSession = useCallback((s: Session) => {
    setReason(null);
    setSessionState(s);
  }, []);

  // Configure synchronously (not in an effect): child pages fetch in their own effects, which run before ours.
  configureClient(
    () => {
      const s = sessionRef.current;
      if (!s || s.expiresAt * 1000 <= Date.now()) return null;
      return s.token;
    },
    () => {
      if (sessionRef.current) signOut("expired");
    },
  );

  // Proactive expiry check so staff are signed out even while idle.
  useEffect(() => {
    if (!session) return;
    const ms = session.expiresAt * 1000 - Date.now();
    const timer = window.setTimeout(() => signOut("expired"), Math.max(0, ms));
    return () => window.clearTimeout(timer);
  }, [session, signOut]);

  const value = useMemo(() => ({ session, signOutReason, setSession, signOut }), [session, signOutReason, setSession, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
