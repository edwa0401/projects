import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { apiRequest } from "../api/client";
import type { AppConfig } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { minutesLeft } from "../lib/format";
import { LogoMark } from "./Creatures";

const ConfigContext = createContext<AppConfig | null>(null);
export const useAppConfig = () => useContext(ConfigContext);

export function Logo() {
  return (
    <span className="logo">
      <LogoMark />
      <span className="logo-text">
        Lead<span className="accent">Rescue</span>
      </span>
    </span>
  );
}

export function ModeBanner({ config }: { config: AppConfig | null }) {
  if (!config) return null;
  if (config.mode === "demo") {
    return (
      <div className="mode-banner mode-demo" role="note">
        <strong>Demo mode</strong>
        <span>Simulated analysis (deterministic rules, not AI) · Synthetic data · Stored locally</span>
      </div>
    );
  }
  return (
    <div className="mode-banner mode-live" role="note">
      <strong>Live AI mode</strong>
      <span>
        Amazon Bedrock · model <code>{config.modelId}</code> · Every reply needs staff approval and is never sent automatically
      </span>
    </div>
  );
}

function SessionClock() {
  const { session } = useAuth();
  const [, tick] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => tick((n) => n + 1), 30000);
    return () => window.clearInterval(t);
  }, []);
  if (!session) return null;
  const mins = minutesLeft(session.expiresAt);
  return <span className="session-clock">Session: {mins} min left</span>;
}

export function AppShell({ children }: { children?: ReactNode }) {
  const { session, signOut } = useAuth();
  const [config, setConfig] = useState<AppConfig | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let alive = true;
    apiRequest<AppConfig>("GET", "/api/config")
      .then((c) => alive && setConfig(c))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const nav = [
    { to: "/", label: "Mission control", end: true },
    { to: "/companions", label: "Companions" },
    { to: "/results", label: "Business results" },
    { to: "/guide", label: "AWS build guide" },
  ];

  return (
    <ConfigContext.Provider value={config}>
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand" aria-label="LeadRescue home">
            <Logo />
            <span className="brand-program">CloudQuest Business Solutions Lab</span>
          </NavLink>
          <nav aria-label="Main" className="mainnav">
            {nav.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : undefined)}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="usermenu">
            <span className="user-name">{config?.user.name ?? session?.user.name}</span>
            <SessionClock />
            <button
              type="button"
              className="btn btn-ghost-light btn-sm"
              onClick={() => {
                signOut("signed_out");
                navigate("/signin");
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <ModeBanner config={config} />
      <main id="main" tabIndex={-1} className="page">
        {children ?? <Outlet />}
      </main>
      <footer className="footer">
        <p>
          LeadRescue is an independent portfolio project from the CloudQuest Business Solutions Lab. Inboxic and all companions are original
          characters. Not affiliated with or endorsed by Nintendo, The Pokémon Company, or Amazon Web Services.
        </p>
      </footer>
    </ConfigContext.Provider>
  );
}
