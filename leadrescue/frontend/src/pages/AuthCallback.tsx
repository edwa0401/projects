import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { completeCognitoSignIn } from "../auth/session";
import { ErrorState, Loading } from "../components/ui";

export function AuthCallbackPage() {
  const { setSession } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    completeCognitoSignIn(window.location.search)
      .then(({ session, returnTo }) => {
        setSession(session);
        navigate(returnTo, { replace: true });
      })
      .catch((e: Error) => setError(e.message));
  }, [navigate, setSession]);

  return (
    <main className="page narrow" id="main">
      {error ? (
        <>
          <ErrorState title="Sign-in failed" message={error} />
          <p>
            <Link to="/signin">Return to sign-in</Link>
          </p>
        </>
      ) : (
        <Loading label="Completing sign-in" />
      )}
    </main>
  );
}
