import type { Role, TokenResponse } from "../api/types";

/*
  Sesión del panel: en memoria (la variable `current`) + copia en sessionStorage.
  sessionStorage sobrevive a recargar la página, pero se borra al cerrar la pestaña (DESIGN §5.2).
  Cualquier script de la página podría leerlo: la defensa real es no tener XSS (React escapa el
  texto) y que el token dure poco (60 min).
*/

export interface Session {
  token: string;
  role: Role; // solo para pintar mientras llega /auth/me; el rol que manda es el de la API
  expiresAt: number; // milisegundos desde 1970, según el reloj de este navegador
}

const STORAGE_KEY = "fernwick.session";

function isSession(value: unknown): value is Session {
  // "type guard": si devuelve true, TypeScript trata `value` como Session
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.token === "string" &&
    (v.role === "admin" || v.role === "demo") &&
    typeof v.expiresAt === "number"
  );
}

function load(): Session | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    // Algo raro o ya vencido: se descarta
    if (!isSession(parsed) || parsed.expiresAt <= Date.now()) {
      sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    // sessionStorage puede no estar disponible (modo privado estricto): queda solo en memoria
    return null;
  }
}

let current: Session | null = load();

export function getSession(): Session | null {
  return current;
}

export function saveSession(response: TokenResponse): Session {
  /*
    Se calcula el vencimiento con expires_in (segundos) y el reloj local, en vez de leer `exp`
    dentro del token: así no hace falta decodificar el JWT en el navegador, y si el reloj
    de la PC está adelantado o atrasado, la cuenta igual dura lo correcto.
  */
  current = {
    token: response.access_token,
    role: response.role,
    expiresAt: Date.now() + response.expires_in * 1000,
  };
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(current));
  } catch {
    // Sin sessionStorage la sesión vive solo en memoria (se pierde al recargar)
  }
  return current;
}

export function clearSession(): void {
  current = null;
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // nada que borrar
  }
}
