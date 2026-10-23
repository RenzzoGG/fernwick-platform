import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { ErrorState, LoadingState } from "../components/States";
import { useAuth } from "./AuthContext";

/** Ruta protegida: sin sesión, al login; con sesión, espera a /auth/me antes de mostrar la página. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { session, user, userError, signOutReason, retryUser, signOut } = useAuth();
  const location = useLocation();

  if (!session) {
    const params = new URLSearchParams();
    // Se recuerda dónde estaba para volver después del login (salvo si salió a propósito)
    if (signOutReason !== "manual") params.set("next", location.pathname + location.search);
    if (signOutReason === "expired") params.set("reason", "expired");
    const query = params.size > 0 ? `?${params}` : "";
    return <Navigate to={`/login${query}`} replace />;
  }

  if (userError) {
    return (
      <div className="mx-auto max-w-md px-4 py-16">
        <ErrorState title="Couldn't load your session" message={userError} onRetry={retryUser}>
          <button type="button" className="min-h-11 px-2 font-semibold text-brand-700 hover:underline" onClick={() => signOut("manual")}>
            Sign out
          </button>
        </ErrorState>
      </div>
    );
  }

  if (!user) return <LoadingState label="Checking your session…" />;

  return children;
}
