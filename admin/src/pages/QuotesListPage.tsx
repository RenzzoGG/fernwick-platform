import { useEffect, useId, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { ApiError } from "../api/client";
import { listQuotes } from "../api/quotes";
import {
  PAGE_SIZE,
  QUOTE_SORTS,
  QUOTE_STATUSES,
  SEARCH_MAX,
  SEARCH_MIN,
  type QuoteListParams,
  type QuoteSort,
  type QuoteStatus,
  type QuoteSummary,
} from "../api/types";
import { Pagination } from "../components/Pagination";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";
import { HOME_SIZE_LABELS, SERVICE_LABELS, SORT_LABELS, STATUS_LABELS, formatDate, formatDateTime } from "../lib/format";
import { useFocusOnMount, usePageTitle } from "../lib/hooks";
import { useRequest } from "../lib/useRequest";
import { buttonPrimary, buttonSecondary, cardClass, inputClass, labelClass, linkClass } from "../lib/ui";

const PAGE_MAX = 10_000; // el mismo tope de la API

// "Type guards" para leer la URL: un valor desconocido se ignora en vez de provocar un 422
function isStatus(value: string | null): value is QuoteStatus {
  return QUOTE_STATUSES.includes(value as QuoteStatus);
}
function isSort(value: string | null): value is QuoteSort {
  return QUOTE_SORTS.includes(value as QuoteSort);
}

/** Lee los filtros desde la URL (?status=new&q=ana&sort=created_at&page=2) y los valida. */
function readParams(searchParams: URLSearchParams): Required<Pick<QuoteListParams, "page" | "sort">> & QuoteListParams {
  const status = searchParams.get("status");
  const sort = searchParams.get("sort");
  const q = (searchParams.get("q") ?? "").trim();
  const page = Number(searchParams.get("page") ?? "1");
  return {
    status: isStatus(status) ? status : undefined,
    q: q.length >= SEARCH_MIN ? q.slice(0, SEARCH_MAX) : undefined,
    sort: isSort(sort) ? sort : "-created_at",
    page: Number.isInteger(page) && page >= 1 && page <= PAGE_MAX ? page : 1,
    page_size: PAGE_SIZE,
  };
}

export function QuotesListPage() {
  usePageTitle("Quotes");
  const headingRef = useFocusOnMount<HTMLHeadingElement>();
  const [searchParams, setSearchParams] = useSearchParams();
  const params = readParams(searchParams);
  const hasFilters = params.status !== undefined || params.q !== undefined;

  // La query string normalizada identifica la petición: si cambia, useRequest vuelve a pedir
  const requestKey = JSON.stringify(params);
  const { data, error, loading, retry } = useRequest((signal) => listQuotes(params, signal), requestKey, true);

  // Al cambiar de página, volver arriba (si no, quedaría al final de la tabla)
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [params.page]);

  /** Copia de la URL actual con cambios; cualquier cambio de filtro vuelve a la página 1. */
  function withChanges(changes: Record<string, string | undefined>): URLSearchParams {
    const nextParams = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(changes)) {
      if (value === undefined || value === "") nextParams.delete(key);
      else nextParams.set(key, value);
    }
    if (!("page" in changes)) nextParams.delete("page");
    return nextParams;
  }

  function clearFilters() {
    setSearchParams(withChanges({ status: undefined, q: undefined }));
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 ref={headingRef} tabIndex={-1} className="font-display text-2xl font-bold text-ink-900 sm:text-3xl">
            Quotes
          </h1>
          <p className="mt-1 text-ink-600">Quote requests from the website, newest first by default.</p>
        </div>
      </div>

      <Filters
        key={params.q ?? ""}
        status={params.status}
        sort={params.sort}
        q={params.q ?? ""}
        onStatus={(status) => setSearchParams(withChanges({ status }))}
        onSort={(sort) => setSearchParams(withChanges({ sort: sort === "-created_at" ? undefined : sort }))}
        onSearch={(q) => setSearchParams(withChanges({ q }))}
      />

      <section aria-labelledby="results-heading" aria-busy={loading} className="mt-6">
        <h2 id="results-heading" className="sr-only">
          Results
        </h2>
        {/* Anuncia el número de resultados al filtrar (aria-live), sin mover el foco */}
        <p aria-live="polite" className="mb-3 text-sm text-ink-600">
          {loading && data ? "Updating…" : data ? `${data.total} ${data.total === 1 ? "quote" : "quotes"}${hasFilters ? " found" : ""}` : ""}
        </p>

        {error ? (
          <ErrorState
            title="Couldn't load quotes"
            message={error instanceof ApiError ? error.message : "Something went wrong."}
            onRetry={retry}
          />
        ) : !data ? (
          <LoadingState label="Loading quotes…" />
        ) : data.items.length === 0 ? (
          data.total > 0 ? (
            <EmptyState title="This page is empty">
              <Link to={{ search: withChanges({ page: undefined }).toString() }} className={linkClass}>
                Go to the first page
              </Link>
            </EmptyState>
          ) : hasFilters ? (
            <EmptyState title="No quotes match these filters">
              <p>Try a different search or status.</p>
              <button type="button" className={`${buttonSecondary} mt-4`} onClick={clearFilters}>
                Clear filters
              </button>
            </EmptyState>
          ) : (
            <EmptyState title="No quotes yet">
              <p>New requests from the website form will show up here.</p>
            </EmptyState>
          )
        ) : (
          <div className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>
            <QuotesTable quotes={data.items} listSearch={searchParams.toString()} />
            <QuotesCards quotes={data.items} listSearch={searchParams.toString()} />
            <Pagination
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
              hrefFor={(page) => `?${withChanges({ page: page === 1 ? undefined : String(page) })}`}
            />
          </div>
        )}
      </section>
    </div>
  );
}

interface FiltersProps {
  status: QuoteStatus | undefined;
  sort: QuoteSort;
  q: string;
  onStatus: (status: QuoteStatus | undefined) => void;
  onSort: (sort: QuoteSort) => void;
  onSearch: (q: string | undefined) => void;
}

/*
  key={q} en el padre: si la búsqueda de la URL cambia desde afuera (Atrás, "Clear filters"),
  React crea un Filters nuevo y el campo toma el valor de la URL.
*/
function Filters({ status, sort, q, onStatus, onSort, onSearch }: FiltersProps) {
  const [draft, setDraft] = useState(q);
  const [hint, setHint] = useState<string | null>(null);
  const hintId = useId();

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = draft.trim();
    // La API exige 2+ caracteres: se avisa aquí en vez de mandar una petición que daría 422
    if (value.length > 0 && value.length < SEARCH_MIN) {
      setHint(`Type at least ${SEARCH_MIN} characters.`);
      return;
    }
    setHint(null);
    onSearch(value || undefined);
  }

  return (
    <div className={`${cardClass} grid gap-4 p-4 md:grid-cols-[1fr_auto_auto] md:items-end`}>
      <form role="search" onSubmit={handleSearch} aria-label="Search quotes">
        <label htmlFor="search" className={labelClass}>
          Search
        </label>
        <div className="flex gap-2">
          <input
            id="search"
            type="search"
            value={draft}
            maxLength={SEARCH_MAX}
            onChange={(e) => {
              setDraft(e.target.value);
              if (hint) setHint(null);
            }}
            placeholder="Name, email or phone"
            aria-invalid={hint ? true : undefined}
            aria-describedby={hint ? hintId : undefined}
            className={inputClass}
          />
          <button type="submit" className={buttonPrimary}>
            Search
          </button>
        </div>
        {hint && (
          <p id={hintId} className="mt-1 text-sm text-danger-600">
            {hint}
          </p>
        )}
      </form>

      <div>
        <label htmlFor="status" className={labelClass}>
          Status
        </label>
        <select
          id="status"
          value={status ?? ""}
          onChange={(e) => onStatus(isStatus(e.target.value) ? e.target.value : undefined)}
          className={`${inputClass} md:w-44`}
        >
          <option value="">All statuses</option>
          {QUOTE_STATUSES.map((value) => (
            <option key={value} value={value}>
              {STATUS_LABELS[value]}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="sort" className={labelClass}>
          Sort by
        </label>
        <select
          id="sort"
          value={sort}
          onChange={(e) => isSort(e.target.value) && onSort(e.target.value)}
          className={`${inputClass} md:w-56`}
        >
          {QUOTE_SORTS.map((value) => (
            <option key={value} value={value}>
              {SORT_LABELS[value]}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

interface QuotesViewProps {
  quotes: QuoteSummary[];
  listSearch: string; // filtros actuales, para que el detalle pueda volver a ellos
}

/** Escritorio (md y más): tabla semántica. */
function QuotesTable({ quotes, listSearch }: QuotesViewProps) {
  return (
    <div className={`${cardClass} hidden overflow-hidden md:block`}>
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Quote requests</caption>
        <thead className="border-b border-ink-200 bg-ink-50 text-xs tracking-wide text-ink-600 uppercase">
          <tr>
            <th scope="col" className="px-4 py-3 font-semibold">Customer</th>
            <th scope="col" className="px-4 py-3 font-semibold">Phone</th>
            <th scope="col" className="px-4 py-3 font-semibold">Service</th>
            <th scope="col" className="px-4 py-3 font-semibold">Preferred date</th>
            <th scope="col" className="px-4 py-3 font-semibold">Status</th>
            <th scope="col" className="px-4 py-3 font-semibold">Received</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-200">
          {quotes.map((quote) => (
            <tr key={quote.id} className="hover:bg-ink-50">
              <td className="px-4 py-3">
                <Link to={`/quotes/${quote.id}`} state={{ listSearch }} className={`${linkClass} text-base`}>
                  {quote.name}
                </Link>
                <div className="break-all text-ink-600">{quote.email}</div>
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-ink-700">{quote.phone}</td>
              <td className="px-4 py-3 text-ink-700">
                <div className="font-medium text-ink-900">{SERVICE_LABELS[quote.service] ?? quote.service}</div>
                <div className="text-ink-600">{HOME_SIZE_LABELS[quote.home_size] ?? quote.home_size}</div>
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-ink-700">{formatDate(quote.preferred_date)}</td>
              <td className="px-4 py-3">
                <StatusBadge status={quote.status} />
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-ink-600">{formatDateTime(quote.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Celular: tarjetas apiladas con la misma información (sin scroll horizontal). */
function QuotesCards({ quotes, listSearch }: QuotesViewProps) {
  return (
    <ul className="space-y-3 md:hidden">
      {quotes.map((quote) => (
        <li key={quote.id} className={`${cardClass} relative p-4 hover:border-brand-300`}>
          <div className="flex items-start justify-between gap-3">
            {/* after:absolute after:inset-0: toda la tarjeta es tocable, pero el único elemento enfocable es el link */}
            <Link
              to={`/quotes/${quote.id}`}
              state={{ listSearch }}
              className="text-base font-semibold text-brand-700 after:absolute after:inset-0 after:rounded-xl"
            >
              {quote.name}
            </Link>
            <StatusBadge status={quote.status} />
          </div>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-ink-500">Service</dt>
            <dd className="text-ink-900">
              {SERVICE_LABELS[quote.service] ?? quote.service} · {HOME_SIZE_LABELS[quote.home_size] ?? quote.home_size}
            </dd>
            <dt className="text-ink-500">Preferred</dt>
            <dd className="text-ink-900">{formatDate(quote.preferred_date)}</dd>
            <dt className="text-ink-500">Contact</dt>
            <dd className="min-w-0 break-all text-ink-700">
              {quote.email}
              <br />
              {quote.phone}
            </dd>
            <dt className="text-ink-500">Received</dt>
            <dd className="text-ink-700">{formatDateTime(quote.created_at)}</dd>
          </dl>
        </li>
      ))}
    </ul>
  );
}
