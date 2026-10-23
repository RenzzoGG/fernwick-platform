import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { QuoteDetailPage } from "./pages/QuoteDetailPage";
import { QuotesListPage } from "./pages/QuotesListPage";

/*
  Rutas del panel. BrowserRouter usa URLs normales (/quotes/42) con la History API del navegador;
  en Railway, Caddy responde index.html a cualquier ruta (modo SPA) y React decide qué mostrar.
*/
export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          {/* Ruta "de diseño" sin path: todo lo de adentro exige sesión y comparte el Layout */}
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/quotes" replace />} />
            <Route path="quotes" element={<QuotesListPage />} />
            <Route path="quotes/:id" element={<QuoteDetailPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
