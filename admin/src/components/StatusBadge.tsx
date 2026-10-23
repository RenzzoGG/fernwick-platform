import type { QuoteStatus } from "../api/types";
import { STATUS_LABELS } from "../lib/format";

// El color ayuda a escanear la lista, pero el texto siempre está (no se depende solo del color)
const STATUS_CLASSES: Record<QuoteStatus, string> = {
  new: "bg-sky-100 text-sky-700 ring-sky-200",
  contacted: "bg-sun-50 text-sun-800 ring-sun-200",
  scheduled: "bg-brand-50 text-brand-800 ring-brand-200",
  closed: "bg-ink-100 text-ink-600 ring-ink-300",
};

export function StatusBadge({ status }: { status: QuoteStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-semibold whitespace-nowrap ring-1 ring-inset ${STATUS_CLASSES[status] ?? STATUS_CLASSES.closed}`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}
