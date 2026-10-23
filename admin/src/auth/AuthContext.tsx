import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getMe } from "../api/auth";
import { ApiError, isAbortError, setUnauthorizedHandler } from "../api/client";
import type { CurrentUser, TokenResponse } from "../api/types";
import { clearSession, getSession, saveSession, type Session } from "./session";

/*
  Contexto de React: guarda la sesión en un solo lugar y cualquier componente la lee con useAuth(),
  sin pasarla de padre a hijo por props.
*/

// "manual": el usuario pulsó Sign out. "expired": venció el token o la API respondió 401.
export type SignOutReason = "manual" | "expired";

interface AuthContextValue {
  session: Session | null;
  user: CurrentUser | null; // null mientras se confirma la sesión con /auth/me
  userError: string | null; // /auth/me falló por algo que no es 401 (p. ej. la API está caída)
  signOutReason: SignOutReason | null;
  signIn: (response: TokenResponse) => Promise<void>;
  signOut: (reason: SignOutReason) => void;
  retryUser: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(getSession);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [userError, setUserError] = useState<string | null>(null);
  const [signOutReason, setSignOutReason] = useState<SignOutReason | null>(null);
  const [userAttempt, setUserAttempt] = useState(0);

  const signOut = useCallback((reason: SignOutReason) => {
    clearSession();
    setSession(null);
    setUser(null);
    setUserError(null);
    setSignOutReason(reason);
  }, []);

  const signIn = useCallback(async (response: TokenResponse) => {
    const newSession = saveSession(response);
    try {
      // Se confirma el usuario antes de entrar: el rol que manda es el de la base, no el de la respuesta
      const me = await getMe();
      setUser(me);
      setUserError(null);
      setSignOutReason(null);
      setSession(newSession);
    } catch (error) {
      clearSession();
      throw error;
    }
  }, []);

  // Cualquier 401 de una petición autenticada cierra la sesión (ver api/client.ts)
  useEffect(() => {
    setUnauthorizedHandler(() => signOut("expired"));
    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  // Sesión guardada de antes (recargar la página): se confirma con /auth/me
  useEffect(() => {
    if (!session || user) return;
    const controller = new AbortController();
    getMe(controller.signal)
      .then((me) => {
        setUser(me);
        setUserError(null);
      })
      .catch((error: unknown) => {
        // El 401 ya lo manejó setUnauthorizedHandler; una cancelación no es error
        if (isAbortError(error) || (error instanceof ApiError && error.status === 401)) return;
        setUserError(error instanceof ApiError ? error.message : "Something went wrong.");
      });
    // Al desmontar o si cambia la sesión, se cancela la petición en curso
    return () => controller.abort();
  }, [session, user, userAttempt]);

  // Cierra la sesión justo cuando vence el token, sin esperar a que una petición falle
  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(() => signOut("expired"), Math.max(0, session.expiresAt - Date.now()));
    return () => window.clearTimeout(timer);
  }, [session, signOut]);

  const retryUser = useCallback(() => {
    setUserError(null);
    setUserAttempt((n) => n + 1);
  }, []);

  // useMemo: el objeto solo cambia si cambia algún valor (evita renders de más en los consumidores)
  const value = useMemo(
    () => ({ session, user, userError, signOutReason, signIn, signOut, retryUser }),
    [session, user, userError, signOutReason, signIn, signOut, retryUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth() debe usarse dentro de <AuthProvider>");
  return context;
}

/** Solo rutas internas: "/quotes?x=1" sí; "//evil.com" o "https://…" no (redirección abierta). */
export function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return "/quotes";
  if (raw.startsWith("/login")) return "/quotes";
  return raw;
}
