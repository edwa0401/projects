import { useEffect, useRef, type ReactNode } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AppShell } from "./components/AppShell";
import { ToastProvider } from "./components/ui";
import { AuthCallbackPage } from "./pages/AuthCallback";
import { BuildGuidePage } from "./pages/BuildGuide";
import { CompanionsPage } from "./pages/Companions";
import { InquiryWorkspacePage } from "./pages/InquiryWorkspace";
import { MissionControlPage } from "./pages/MissionControl";
import { NewInquiryPage } from "./pages/NewInquiry";
import { ResultsPage } from "./pages/Results";
import { SignInPage } from "./pages/SignIn";

function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const location = useLocation();
  if (!session) return <Navigate to="/signin" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

const TITLES: Record<string, string> = {
  "/": "Mission control",
  "/companions": "Companions",
  "/results": "Business results",
  "/guide": "AWS build guide",
  "/inquiries/new": "New inquiry",
  "/signin": "Sign in",
};

/** Updates the document title and moves focus to main content on route change (screen reader friendly). */
function RouteAnnouncer() {
  const location = useLocation();
  const firstLoad = useRef(true);
  useEffect(() => {
    const title = TITLES[location.pathname] ?? (location.pathname.startsWith("/inquiries/") ? "Inquiry" : "LeadRescue");
    document.title = `${title} | LeadRescue`;
    if (firstLoad.current) {
      firstLoad.current = false; // keep natural focus order on a fresh load so the skip link is the first Tab stop
      return;
    }
    const main = document.getElementById("main");
    if (main && document.activeElement !== main && !location.pathname.startsWith("/signin")) main.focus({ preventScroll: true });
  }, [location.pathname]);
  return null;
}

function NotFound() {
  return (
    <div className="narrow">
      <h1>Page not found</h1>
      <p>
        <Link to="/">Go to mission control</Link>
      </p>
    </div>
  );
}

export function AppRoutes() {
  return (
    <>
      <RouteAnnouncer />
      <Routes>
        <Route path="/signin" element={<SignInPage />} />
        <Route path="/auth/callback" element={<AuthCallbackPage />} />
        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route index element={<MissionControlPage />} />
          <Route path="inquiries/new" element={<NewInquiryPage />} />
          <Route path="inquiries/:id" element={<InquiryWorkspacePage />} />
          <Route path="companions" element={<CompanionsPage />} />
          <Route path="results" element={<ResultsPage />} />
          <Route path="guide" element={<BuildGuidePage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
