import type { ReactNode } from "react";
import { Link, useLocation, useParams } from "react-router";
import { ApiError } from "../api/client";
import { getQuote } from "../api/quotes";
import type { Note, QuoteDetail, StatusChange } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { NoteForm } from "../components/NoteForm";
import { ErrorState, LoadingState } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";
import { StatusControl } from "../components/StatusControl";
import { HOME_SIZE_LABELS, SERVICE_LABELS, STATUS_LABELS, formatDate, formatDateTime } from "../lib/format";
import { useFocusOnMount, usePageTitle } from "../lib/hooks";
import { useRequest } from "../lib/useRequest";
import { cardClass, linkClass } from "../lib/ui";

/** "/quotes/42" → 42. Cualquier otra cosa (abc, -1, 1e3, enormes) → null: "no encontrada" sin llamar a la API. */
function parseId(raw: string | undefined): number | null {
  if (!raw || !/^[1-9]\d*$/.test(raw)) return null;
  const id = Number(raw);
  return Number.isSafeInteger(id) ? id : null;
}

/** La lista manda sus filtros en el "state" del link; si se entró directo por URL, no hay. */
function useBackToList(): string {
  const { state } = useLocation();
  const listSearch = (state as { listSearch?: unknown } | null)?.listSearch;
  return typeof listSearch === "string" && listSearch ? `/quotes?${listSearch}` : "/quotes";
}

export function QuoteDetailPage() {
  const id = parseId(useParams().id);
  const backTo = useBackToList();
  // Solo el admin ve controles de edición (falla cerrado: mientras no se sabe el rol, no hay)
  const canEdit = useAuth().user?.role === "admin";

  const { data, error, loading, retry, setData } = useRequest(
    (signal) => (id === null ? Promise.reject(new ApiError(404, "Not found")) : getQuote(id, signal)),
    String(id),
  );

  const notFound = error instanceof ApiError && (error.status === 404 || error.status === 422);
  usePageTitle(data ? data.name : notFound ? "Quote not found" : "Quote");

  const backLink = (
    <Link to={backTo} className={`${linkClass} inline-flex min-h-11 items-center`}>
      <span aria-hidden="true">←</span>&nbsp;Back to quotes
    </Link>
  );

  let content: ReactNode;
  if (loading) {
    content = <LoadingState label="Loading quote…" />;
  } else if (notFound) {
    // El demo recibe este mismo 404 si pide una cotización real (para él "no existe")
    content = <NotFound backTo={backTo} />;
  } else if (error || !data) {
    content = (
      <ErrorState
        title="Couldn't load this quote"
        message={error instanceof ApiError ? error.message : "Something went wrong."}
        onRetry={retry}
      />
    );
  } else {
    content = <Detail quote={data} canEdit={canEdit} update={setData} />;
  }

  return (
    <div>
      <div className="mb-4">{backLink}</div>
      {content}
    </div>
  );
}

function NotFound({ backTo }: { backTo: string }) {
  const headingRef = useFocusOnMount<HTMLHeadingElement>();
  return (
    <div role="alert" className={`${cardClass} px-5 py-12 text-center`}>
      <h1 ref={headingRef} tabIndex={-1} className="font-display text-2xl font-bold text-ink-900">
        Quote not found
      </h1>
      <p className="mt-2 text-ink-600">It doesn't exist, or the link is wrong.</p>
      <p className="mt-4">
        <Link to={backTo} className={linkClass}>
          Back to quotes
        </Link>
      </p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = `section-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id} className={`${cardClass} p-5`}>
      <h2 id={id} className="mb-3 font-display text-lg font-semibold text-ink-900">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm font-medium text-ink-500">{label}</dt>
      <dd className="mt-0.5 text-ink-900">{children}</dd>
    </div>
  );
}

interface DetailProps {
  quote: QuoteDetail;
  canEdit: boolean;
  // Forma "función" (prev => nuevo): cada escritura parte de los datos más recientes
  update: (fn: (prev: QuoteDetail) => QuoteDetail) => void;
}

function Detail({ quote, canEdit, update }: DetailProps) {
  const headingRef = useFocusOnMount<HTMLHeadingElement>();
  // tel: solo admite dígitos y "+"; (305) 555-0142 → tel:3055550142
  const telHref = `tel:${quote.phone.replace(/[^\d+]/g, "")}`;

  return (
    <article>
      <header className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2">
        <h1 ref={headingRef} tabIndex={-1} className="font-display text-2xl font-bold break-words text-ink-900 sm:text-3xl">
          {quote.name}
        </h1>
        <StatusBadge status={quote.status} />
        <p className="w-full text-sm text-ink-600">
          Quote #{quote.id} · Received <time dateTime={quote.created_at}>{formatDateTime(quote.created_at)}</time>
        </p>
      </header>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Section title="Request">
            <dl className="grid gap-4 sm:grid-cols-3">
              <Field label="Service">{SERVICE_LABELS[quote.service] ?? quote.service}</Field>
              <Field label="Home size">{HOME_SIZE_LABELS[quote.home_size] ?? quote.home_size}</Field>
              <Field label="Preferred date">
                <time dateTime={quote.preferred_date}>{formatDate(quote.preferred_date)}</time>
              </Field>
            </dl>
            <div className="mt-4 border-t border-ink-200 pt-4">
              <h3 className="text-sm font-medium text-ink-500">Message</h3>
              {quote.message ? (
                // Texto plano: React lo escapa (nunca se interpreta como HTML); pre-wrap respeta los saltos de línea
                <p className="mt-1 whitespace-pre-wrap break-words text-ink-900">{quote.message}</p>
              ) : (
                <p className="mt-1 text-ink-500 italic">No message.</p>
              )}
            </div>
          </Section>

          <Section title="Notes">
            <NotesList notes={quote.notes} />
            {canEdit && (
              <NoteForm quoteId={quote.id} onAdded={(note) => update((prev) => ({ ...prev, notes: [...prev.notes, note] }))} />
            )}
          </Section>
        </div>

        <div className="space-y-5">
          <Section title="Contact">
            <dl className="space-y-3">
              <Field label="Email">
                <a href={`mailto:${quote.email}`} className={`${linkClass} break-all`}>
                  {quote.email}
                </a>
              </Field>
              <Field label="Phone">
                <a href={telHref} className={linkClass}>
                  {quote.phone}
                </a>
              </Field>
            </dl>
          </Section>

          {canEdit && (
            <Section title="Change status">
              <StatusControl quote={quote} onChange={(updated) => update(() => updated)} />
            </Section>
          )}

          <Section title="Status history">
            <StatusHistory changes={quote.status_history} />
          </Section>

          <Section title="Record">
            <dl className="space-y-3 text-sm">
              <Field label="Received">
                <time dateTime={quote.created_at}>{formatDateTime(quote.created_at)}</time>
              </Field>
              <Field label="Last updated">
                <time dateTime={quote.updated_at}>{formatDateTime(quote.updated_at)}</time>
              </Field>
            </dl>
          </Section>
        </div>
      </div>
    </article>
  );
}

function NotesList({ notes }: { notes: Note[] }) {
  if (notes.length === 0) return <p className="text-ink-500 italic">No notes yet.</p>;
  return (
    <ol className="space-y-3">
      {notes.map((note) => (
        <li key={note.id} className="rounded-lg border border-ink-200 bg-ink-50 p-3">
          <p className="whitespace-pre-wrap break-words text-ink-900">{note.body}</p>
          <p className="mt-2 text-sm text-ink-600">
            {note.author_email ?? "Deleted user"} · <time dateTime={note.created_at}>{formatDateTime(note.created_at)}</time>
          </p>
        </li>
      ))}
    </ol>
  );
}

function StatusHistory({ changes }: { changes: StatusChange[] }) {
  if (changes.length === 0) return <p className="text-ink-500 italic">No status changes yet.</p>;
  return (
    <ol className="space-y-3 border-l-2 border-ink-200 pl-4">
      {changes.map((change) => (
        <li key={change.changed_at + change.to_status} className="text-sm">
          <p className="font-medium text-ink-900">
            {STATUS_LABELS[change.from_status] ?? change.from_status} <span aria-hidden="true">→</span>
            <span className="sr-only">to</span> {STATUS_LABELS[change.to_status] ?? change.to_status}
          </p>
          <p className="text-ink-600">
            {change.changed_by_email ?? "Deleted user"} · <time dateTime={change.changed_at}>{formatDateTime(change.changed_at)}</time>
          </p>
        </li>
      ))}
    </ol>
  );
}
