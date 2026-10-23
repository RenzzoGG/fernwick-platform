import { Link, NavLink, Outlet } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { buttonSecondary } from "../lib/ui";
import { DemoBanner } from "./DemoBanner";
import { Logo } from "./Logo";

/** Marco de las páginas privadas: banner demo, encabezado y <main>. <Outlet /> = la página actual. */
export function Layout() {
  const { user, signOut } = useAuth();
  const isDemo = user?.role !== "admin"; // falla cerrado, como scope_is_demo de la API

  return (
    <div className="min-h-dvh">
      {/* Primer elemento con Tab: salta el encabezado y va directo al contenido */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:font-semibold focus:text-brand-700 focus:shadow"
      >
        Skip to content
      </a>
      {isDemo && <DemoBanner />}
      <header className="border-b border-ink-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3">
          <div className="flex items-center gap-6">
            <Link to="/quotes" className="flex items-center gap-2 rounded-lg">
              <Logo />
              <span className="font-display text-lg font-bold text-ink-900">
                Fernwick <span className="font-semibold text-brand-700">Admin</span>
              </span>
            </Link>
            <nav aria-label="Main">
              <NavLink
                to="/quotes"
                className={({ isActive }) =>
                  isActive
                    ? "inline-flex min-h-11 items-center border-b-2 border-brand-700 px-1 font-semibold text-ink-900"
                    : "inline-flex min-h-11 items-center border-b-2 border-transparent px-1 font-semibold text-ink-600 hover:text-ink-900"
                }
              >
                Quotes
              </NavLink>
            </nav>
          </div>
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex min-w-0 items-center gap-2 text-sm text-ink-600">
              <span className="sr-only">Signed in as</span>
              <span className="truncate">{user?.email}</span>
              {isDemo && (
                <span className="shrink-0 rounded-full bg-sun-200 px-2 py-0.5 text-xs font-semibold text-sun-800">Demo</span>
              )}
            </span>
            <button type="button" className={buttonSecondary} onClick={() => signOut("manual")}>
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto max-w-6xl px-4 py-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  );
}
