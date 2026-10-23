import { API_URL } from "../config";
import { getSession } from "../auth/session";

/** Error de la API con su código HTTP. status 0 = no hubo respuesta (red caída, CORS, API apagada). */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

/*
  Qué hacer cuando una petición autenticada recibe 401 (token vencido, manipulado o usuario
  desactivado). Lo registra AuthContext: cierra la sesión y manda al login. Así ninguna página
  tiene que acordarse de manejarlo.
*/
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

/*
  Lo mismo para el 403: la API lo responde cuando un usuario sin permiso (el demo) intenta escribir.
  La interfaz del demo no muestra botones de edición, pero si alguien fuerza la escritura (desde la
  consola, o porque su rol cambió en la base con la página abierta), AuthContext muestra un aviso.
*/
let onForbidden: (() => void) | null = null;

export function setForbiddenHandler(handler: (() => void) | null): void {
  onForbidden = handler;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  auth?: boolean; // true (por defecto): manda el token y trata el 401 como "sesión vencida"
  signal?: AbortSignal;
}

function detailMessage(data: unknown): string | null {
  // Formato de FastAPI: {"detail": "texto"} o, en 422, {"detail": [{"msg": "..."}]}
  if (typeof data !== "object" || data === null || !("detail" in data)) return null;
  const detail = (data as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg;
  return null;
}

/** fetch con la URL base, el token y errores tipados. Devuelve el JSON ya tipado como T. */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, signal } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const session = auth ? getSession() : null;
  if (auth) {
    if (!session) {
      onUnauthorized?.();
      throw new ApiError(401, "Not signed in.");
    }
    headers.Authorization = `Bearer ${session.token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    // Una petición cancelada no es un error que mostrar: se relanza tal cual
    if (isAbortError(error)) throw error;
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }

  // Algunas respuestas de error pueden no traer JSON (p. ej. un 502 del proxy)
  const data: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    if (response.status === 401 && auth) onUnauthorized?.();
    if (response.status === 403 && auth) onForbidden?.();
    throw new ApiError(response.status, detailMessage(data) ?? `Request failed (${response.status}).`);
  }
  return data as T;
}
