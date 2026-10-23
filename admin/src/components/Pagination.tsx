import { Link } from "react-router";

interface Props {
  page: number;
  pageSize: number;
  total: number;
  hrefFor: (page: number) => string; // URL (?…&page=N) de una página
}

const linkClasses =
  "inline-flex min-h-11 items-center rounded-lg border border-ink-300 bg-white px-4 font-semibold text-ink-900 hover:bg-ink-100";
const disabledClasses =
  "inline-flex min-h-11 items-center rounded-lg border border-ink-200 bg-ink-50 px-4 font-semibold text-ink-500";

/** Anterior / siguiente como links reales: se pueden abrir en otra pestaña y funciona Atrás. */
export function Pagination({ page, pageSize, total, hrefFor }: Props) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize && page === 1) return null;

  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <nav aria-label="Pagination" className="mt-4 flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-ink-600">
        {first <= total ? (
          <>
            Showing <strong className="text-ink-900">{first}</strong>–<strong className="text-ink-900">{last}</strong> of{" "}
            <strong className="text-ink-900">{total}</strong>
          </>
        ) : (
          <>
            Page {page} of {lastPage}
          </>
        )}
      </p>
      <div className="flex gap-2">
        {page > 1 ? (
          <Link to={hrefFor(page - 1)} className={linkClasses} rel="prev">
            <span aria-hidden="true">←</span> Previous
          </Link>
        ) : (
          <span className={disabledClasses} aria-disabled="true">
            <span aria-hidden="true">←</span>&nbsp;Previous
          </span>
        )}
        {page < lastPage ? (
          <Link to={hrefFor(page + 1)} className={linkClasses} rel="next">
            Next <span aria-hidden="true">→</span>
          </Link>
        ) : (
          <span className={disabledClasses} aria-disabled="true">
            Next&nbsp;<span aria-hidden="true">→</span>
          </span>
        )}
      </div>
    </nav>
  );
}
