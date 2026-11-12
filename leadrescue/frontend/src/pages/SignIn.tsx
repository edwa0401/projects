import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { apiRequest, ApiError } from "../api/client";
import type { StaffMember } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { AUTH_MODE, cognitoConfigured, demoSignIn, startCognitoSignIn } from "../auth/session";
import { Logo } from "../components/AppShell";
import { Inboxic } from "../components/Creatures";
import { Alert } from "../components/ui";

export function SignInPage() {
  const { session, setSession, signOutReason } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const [staff, setStaff] = useState<StaffMember[] | null>(null);
  const [selected, setSelected] = useState("");
  const [minutes, setMinutes] = useState(60);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (AUTH_MODE !== "demo") return;
    apiRequest<{ staff: StaffMember[]; sessionMinutes: number }>("GET", "/api/demo/staff", { auth: false })
      .then((r) => {
        setStaff(r.staff);
        setMinutes(r.sessionMinutes);
        setSelected(r.staff[0]?.id ?? "");
      })
      .catch((e: ApiError) => setError(e.message));
  }, []);

  if (session) return <Navigate to={from} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (AUTH_MODE === "cognito") {
        await startCognitoSignIn(from);
        return;
      }
      const s = await demoSignIn(selected);
      setSession(s);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="signin">
      <a href="#signin-form" className="skip-link">
        Skip to sign in
      </a>
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-top">
          <Logo />
          <span className="hero-program">
            CloudQuest
            <br />
            Business Solutions Lab
          </span>
        </div>
        <div className="hero-body">
          <div className="hero-copy">
            <h1 id="hero-title">
              Catch the lead.
              <br />
              <span className="accent-italic">Rescue</span> the opportunity.
            </h1>
            <p className="hero-sub">AI-assisted inquiry triage for a moving company, with a person approving every reply.</p>
            <ul className="feature-chips">
              <li>
                <span className="chip-icon chip-lav" aria-hidden="true">
                  ≡
                </span>
                Classify requests
              </li>
              <li>
                <span className="chip-icon chip-rose" aria-hidden="true">
                  !
                </span>
                Spot urgent issues
              </li>
              <li>
                <span className="chip-icon chip-teal" aria-hidden="true">
                  …
                </span>
                Draft helpful replies
              </li>
            </ul>
            <p className="approval-pill">
              <span aria-hidden="true">✓</span> Human approval before sending
            </p>
          </div>
          <div className="hero-art">
            <Inboxic size={240} />
            <div className="companion-plate">
              <strong>Inboxic</strong>
              <span>Service intelligence</span>
              <span className="plate-move">Priority Mind</span>
            </div>
          </div>
        </div>
      </section>

      <section className="signin-card" aria-labelledby="signin-title">
        <form id="signin-form" onSubmit={onSubmit} noValidate>
          <h2 id="signin-title">Staff sign-in</h2>
          {signOutReason === "expired" && (
            <Alert tone="warning" title="Session expired" role="alert">
              For security, staff sessions expire. Sign in again to continue. Saved drafts are kept.
            </Alert>
          )}
          {signOutReason === "signed_out" && <Alert tone="info">You signed out.</Alert>}
          {error && (
            <Alert tone="danger" title="Could not sign in">
              {error}
            </Alert>
          )}
          {AUTH_MODE === "demo" ? (
            <>
              <p className="muted">
                <strong>Demo sign-in.</strong> Choose a fictional staff profile. No password is used in demo mode. Sessions last {minutes} minutes.
                Deployed environments use Amazon Cognito.
              </p>
              {!staff && !error && <p className="muted">Loading staff profiles…</p>}
              {staff && (
                <fieldset className="radio-list">
                  <legend>Demo staff profile</legend>
                  {staff.map((s) => (
                    <label key={s.id} className="radio-row">
                      <input type="radio" name="staff" value={s.id} checked={selected === s.id} onChange={() => setSelected(s.id)} />
                      <span>
                        <strong>{s.name}</strong>
                        {s.role && <span className="muted"> · {s.role}</span>}
                      </span>
                    </label>
                  ))}
                </fieldset>
              )}
              <button className="btn btn-primary btn-block" type="submit" disabled={busy || !selected}>
                {busy ? "Signing in…" : "Sign in to demo"}
              </button>
            </>
          ) : (
            <>
              <p className="muted">Sign in with your staff account. You will be redirected to the company sign-in page.</p>
              {!cognitoConfigured() && (
                <Alert tone="danger" title="Sign-in is not configured">
                  Set VITE_COGNITO_DOMAIN and VITE_COGNITO_CLIENT_ID when building the frontend.
                </Alert>
              )}
              <button className="btn btn-primary btn-block" type="submit" disabled={busy || !cognitoConfigured()}>
                {busy ? "Redirecting…" : "Sign in with staff account"}
              </button>
            </>
          )}
        </form>
        <p className="fineprint">Project concept · Demo uses simulated analysis · Original characters, no official affiliation.</p>
      </section>
    </div>
  );
}
