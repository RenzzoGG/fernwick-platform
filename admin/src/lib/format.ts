import type { HomeSize, IsoDate, IsoDateTime, QuoteSort, QuoteStatus, Service } from "../api/types";
import { BUSINESS_TIMEZONE } from "../config";

/*
  Etiquetas para mostrar los valores de la API. Record<Service, string> obliga a tener una
  etiqueta por cada valor: si mañana se agrega un servicio en types.ts, el build falla aquí
  hasta que se le ponga nombre.
*/

// Los mismos textos de los <select> de la landing
export const SERVICE_LABELS: Record<Service, string> = {
  standard: "Standard cleaning",
  recurring: "Recurring cleaning",
  deep: "Deep cleaning",
  move: "Move-in / move-out",
  office: "Office cleaning",
  "post-renovation": "Post-renovation",
};

export const HOME_SIZE_LABELS: Record<HomeSize, string> = {
  studio: "Studio / 1 bedroom",
  "2-bed": "2 bedrooms",
  "3-bed": "3 bedrooms",
  "4-bed": "4+ bedrooms",
  office: "Office / commercial space",
};

export const STATUS_LABELS: Record<QuoteStatus, string> = {
  new: "New",
  contacted: "Contacted",
  scheduled: "Scheduled",
  closed: "Closed",
};

export const SORT_LABELS: Record<QuoteSort, string> = {
  "-created_at": "Newest first",
  created_at: "Oldest first",
  preferred_date: "Preferred date (soonest)",
  "-preferred_date": "Preferred date (latest)",
};

// Intl.DateTimeFormat es nativo del navegador: no hace falta una librería de fechas
const dateFormat = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

const dateTimeFormat = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: BUSINESS_TIMEZONE,
});

/**
 * Fecha "pura" (preferred_date): "2026-10-20" → "Oct 20, 2026".
 * Se interpreta y se formatea en UTC: si se usara la zona del navegador, en América
 * "2026-10-20" (medianoche UTC) se mostraría como el 19.
 */
export function formatDate(value: IsoDate): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : dateFormat.format(date);
}

/** Instante (created_at, …) en la hora del negocio: "Oct 20, 2026, 6:40 PM". */
export function formatDateTime(value: IsoDateTime): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateTimeFormat.format(date);
}
