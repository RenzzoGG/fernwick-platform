import { apiFetch } from "./client";
import type { QuoteDetail, QuoteListParams, QuotePage } from "./types";

export function listQuotes(params: QuoteListParams, signal?: AbortSignal): Promise<QuotePage> {
  // URLSearchParams escapa los valores (una búsqueda con "&" o "%" no rompe la URL)
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.size > 0 ? `?${query}` : "";
  return apiFetch<QuotePage>(`/v1/quotes${suffix}`, { signal });
}

export function getQuote(id: number, signal?: AbortSignal): Promise<QuoteDetail> {
  return apiFetch<QuoteDetail>(`/v1/quotes/${id}`, { signal });
}
