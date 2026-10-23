import { useEffect, useRef, useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { login, loginDemo } from "../api/auth";
import { ApiError } from "../api/client";
import { safeNext, useAuth } from "../auth/AuthContext";
import { Logo } from "../components/Logo";
import { usePageTitle } from "../lib/hooks";
import { buttonPrimary, buttonSecondary, cardClass, inputClass, labelClass } from "../lib/ui";

type Pending = "login" | "demo" | null;

// Traduce el error de la API a un mensaje para la persona (sin detalles técnicos)
function loginErrorMessage(error: unknown, kind: "login" | "demo"): string {
  if (!(error instanceof ApiError)) return "Something went wrong. Please try again.";
  switch (error.status) {
    case 0:
      return error.message; // sin conexión con la API
    case 401:
      return "Incorrect email or password.";
    case 404:
      return kind === "demo" ? "The demo isn't available right now." : "Something went wrong. Please try again.";
    case 422:
      return "Enter your email and password.";
    case 429:
      // El header Retry-After no es visible desde el navegador (CORS no lo expone)
      return "Too many attempts. Please wait a minute and try again.";
    default:
      return "The server had a problem. Please try again in a moment.";
  }
}

export function LoginPage() {
  usePageTitle("Sign in");
  const { session, user, signIn } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = safeNext(searchParams.get("next"));
  const expired = searchParams.get("reason") === "expired";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState<Pending>(null);
  const [error, setError] = useState<string | null>(null);
  const errorRef = useRef<HTMLDivElement>(null);

  // Al aparecer un error, el foco va al mensaje (lo lee el lector de pantalla y se ve)
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  // Ya hay sesión (p. ej. abrió /login a mano): directo al panel
  if (session && user && !pending) return <Navigate to={next} replace />;

  async function enter(kind: "login" | "demo", request: () => ReturnType<typeof login>) {
    setPending(kind);
    setError(null);
    try {
      await signIn(await request());
      navigate(next, { replace: true });
    } catch (err) {
      setError(loginErrorMessage(err, kind));
      setPending(null);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); // sin esto el navegador recargaría la página con el formulario
    void enter("login", () => login(email, password));
  }

  return (
    <div className="flex min-h-dvh items-center justify-center px-4 py-10">
      <main className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <Logo className="size-12" />
          <h1 className="font-display text-2xl font-bold text-ink-900">Fernwick Admin</h1>
          <p className="text-ink-600">Sign in to manage cleaning quotes.</p>
        </div>

        {expired && !error && (
          <p role="status" className="mb-4 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700">
            Your session has expired. Please sign in again.
          </p>
        )}

        {error && (
          <div
            ref={errorRef}
            tabIndex={-1}
            role="alert"
            className="mb-4 rounded-lg border border-danger-600/30 bg-danger-50 px-4 py-3 text-sm font-medium text-danger-600"
          >
            {error}
          </div>
        )}

        <div className={`${cardClass} p-6`}>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className={labelClass}>
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="password" className={labelClass}>
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
              />
            </div>
            <button type="submit" className={`${buttonPrimary} w-full`} disabled={pending !== null}>
              {pending === "login" ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <div className="my-5 flex items-center gap-3 text-sm text-ink-500" aria-hidden="true">
            <span className="h-px flex-1 bg-ink-200" />
            or
            <span className="h-px flex-1 bg-ink-200" />
          </div>

          <button
            type="button"
            className={`${buttonSecondary} w-full`}
            disabled={pending !== null}
            onClick={() => void enter("demo", loginDemo)}
            aria-describedby="demo-hint"
          >
            {pending === "demo" ? "Opening demo…" : "View demo"}
          </button>
          <p id="demo-hint" className="mt-2 text-center text-sm text-ink-600">
            Read-only, with fictional data. No password needed.
          </p>
        </div>
      </main>
    </div>
  );
}
