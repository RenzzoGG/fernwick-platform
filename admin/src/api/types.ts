/*
  Tipos de la API, escritos a mano a partir de api/app/schemas/ (quote.py y auth.py).
  Si la API cambia un esquema, se actualiza este archivo en el mismo commit.

  Las listas van como `as const` para usarlas en tiempo de ejecución (opciones de un <select>)
  y, a la vez, derivar el tipo: `(typeof X)[number]` es la unión de sus valores.
*/

// Mismos valores que api/app/models/base.py
export const USER_ROLES = ["admin", "demo"] as const;
export const QUOTE_STATUSES = ["new", "contacted", "scheduled", "closed"] as const;
export const SERVICES = ["standard", "recurring", "deep", "move", "office", "post-renovation"] as const;
export const HOME_SIZES = ["studio", "2-bed", "3-bed", "4-bed", "office"] as const;
// QuoteSort en schemas/quote.py: "-" = descendente
export const QUOTE_SORTS = ["-created_at", "created_at", "preferred_date", "-preferred_date"] as const;

export type Role = (typeof USER_ROLES)[number];
export type QuoteStatus = (typeof QUOTE_STATUSES)[number];
export type Service = (typeof SERVICES)[number];
export type HomeSize = (typeof HOME_SIZES)[number];
export type QuoteSort = (typeof QUOTE_SORTS)[number];

// JSON no tiene tipo fecha: llegan como texto ISO 8601
export type IsoDate = string; // "2026-10-20"
export type IsoDateTime = string; // "2026-10-20T22:40:00Z" (siempre en UTC)

/** TokenResponse: respuesta de POST /v1/auth/login y /v1/auth/demo. */
export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number; // segundos
  role: Role;
}

/** CurrentUser: GET /v1/auth/me. */
export interface CurrentUser {
  id: number;
  email: string;
  role: Role;
}

/** QuoteListParams: parámetros de GET /v1/quotes (todos opcionales). */
export interface QuoteListParams {
  status?: QuoteStatus;
  q?: string; // 2 a 100 caracteres
  page?: number;
  page_size?: number;
  sort?: QuoteSort;
}

/** QuoteSummary: una fila de la lista. */
export interface QuoteSummary {
  id: number;
  name: string;
  email: string;
  phone: string;
  service: Service;
  home_size: HomeSize;
  preferred_date: IsoDate;
  status: QuoteStatus;
  created_at: IsoDateTime;
}

/** QuotePage: GET /v1/quotes. */
export interface QuotePage {
  items: QuoteSummary[];
  total: number; // filas que cumplen los filtros, en todas las páginas
  page: number;
  page_size: number;
}

/** NoteOut */
export interface Note {
  id: number;
  body: string;
  author_email: string | null; // null si el autor fue eliminado
  created_at: IsoDateTime;
}

/** StatusChangeOut */
export interface StatusChange {
  from_status: QuoteStatus;
  to_status: QuoteStatus;
  changed_by_email: string | null;
  changed_at: IsoDateTime;
}

/** QuoteDetail: GET /v1/quotes/{id}. `extends` = QuoteSummary + estos campos. */
export interface QuoteDetail extends QuoteSummary {
  message: string | null;
  updated_at: IsoDateTime;
  notes: Note[];
  status_history: StatusChange[];
}

// Constantes de validación del panel (las mismas de la API, para no mandar un 422 evitable)
export const SEARCH_MIN = 2;
export const SEARCH_MAX = 100;
export const PAGE_SIZE = 20;
export const NOTE_BODY_MAX = 2000; // NOTE_BODY_MAX de models/base.py (el mismo del CHECK)

/** DailyCount: un día de last_30_days. */
export interface DailyCount {
  date: IsoDate;
  count: number;
}

/** MetricsSummary: GET /v1/metrics/summary. La API manda todas las claves, aunque valgan 0. */
export interface MetricsSummary {
  total: number;
  by_status: Record<QuoteStatus, number>;
  by_service: Record<Service, number>;
  last_30_days: DailyCount[]; // del más antiguo a hoy, sin huecos
}
