// En desarrollo, si falta VITE_API_URL, se usa la API local. En el build de producción
// vite.config.ts exige la variable, así nunca se publica un panel apuntando a localhost.
export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

// Zona del negocio ficticio: la misma BUSINESS_TIMEZONE de la API (fechas de la lista y del detalle)
export const BUSINESS_TIMEZONE = "America/New_York";
