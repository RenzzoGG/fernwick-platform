import { apiFetch } from "./client";
import type { CurrentUser, TokenResponse } from "./types";

// auth: false: estas rutas no llevan token, y su 401 es "contraseña incorrecta", no "sesión vencida"
export function login(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/v1/auth/login", {
    method: "POST",
    body: { email, password },
    auth: false,
  });
}

export function loginDemo(): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/v1/auth/demo", { method: "POST", auth: false });
}

export function getMe(signal?: AbortSignal): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/v1/auth/me", { signal });
}
