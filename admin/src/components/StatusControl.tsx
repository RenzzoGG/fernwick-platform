import { useId, useRef, useState } from "react";
import { ApiError } from "../api/client";
import { changeQuoteStatus, getQuote } from "../api/quotes";
import { QUOTE_STATUSES, type QuoteDetail, type QuoteStatus } from "../api/types";
import { STATUS_LABELS } from "../lib/format";
import { buttonPrimary, buttonSecondary, inputClass, labelClass } from "../lib/ui";

type Feedback = { kind: "success" | "info" | "error"; text: string } | null;

const FEEDBACK_CLASSES = {
  success: "text-brand-800",
  info: "text-sun-800",
  error: "text-danger-600",
} as const;

interface Props {
  quote: QuoteDetail;
  onChange: (quote: QuoteDetail) => void; // reemplaza el detalle en la página (sin recargar)
}

/**
 * Cambio de estado (solo admin; la página no lo muestra al demo).
 * Flujo: elegir en el <select> → "Change status" → confirmar en un <dialog> → PATCH.
 */
export function StatusControl({ quote, onChange }: Props) {
  const selectId = useId();
  const dialogRef = useRef<HTMLDialogElement>(null);
  // Cerrojo contra el doble clic: un ref cambia al instante, el estado de React recién en el próximo render
  const savingRef = useRef(false);
  const [selected, setSelected] = useState<QuoteStatus>(quote.status);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);

  const unchanged = selected === quote.status;

  function openConfirm() {
    if (unchanged || savingRef.current) return;
    setFeedback(null);
    // showModal(): bloquea el resto de la página, atrapa el foco y cierra con Esc
    dialogRef.current?.showModal();
  }

  async function confirm() {
    dialogRef.current?.close();
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    const target = selected;
    try {
      const updated = await changeQuoteStatus(quote.id, target);
      onChange(updated);
      setSelected(updated.status);
      setFeedback({ kind: "success", text: `Status changed to ${STATUS_LABELS[updated.status]}.` });
    } catch (error) {
      await handleError(error, target);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  async function handleError(error: unknown, target: QuoteStatus) {
    if (!(error instanceof ApiError)) {
      setFeedback({ kind: "error", text: "Something went wrong. Please try again." });
      return;
    }
    switch (error.status) {
      case 409:
        // Ya tenía ese estado: casi seguro otro admin lo cambió. Se trae lo último para mostrarlo.
        try {
          const latest = await getQuote(quote.id);
          onChange(latest);
          setSelected(latest.status);
        } catch {
          // Si falla la relectura, queda el aviso igual
        }
        setFeedback({
          kind: "info",
          text: `This quote is already ${STATUS_LABELS[target]} — it may have been changed by someone else. Showing the latest data.`,
        });
        return;
      case 403:
        // El aviso grande lo muestra el Layout (setForbiddenHandler); aquí, el contexto del formulario
        setFeedback({ kind: "error", text: "Your account can't change quotes (read-only)." });
        return;
      case 404:
        setFeedback({ kind: "error", text: "This quote no longer exists." });
        return;
      case 401:
        return; // la sesión venció: AuthContext ya manda al login
      default:
        setFeedback({ kind: "error", text: `${error.message} Please try again.` });
    }
  }

  return (
    <div>
      <label htmlFor={selectId} className={labelClass}>
        New status
      </label>
      <div className="flex flex-wrap gap-2">
        <select
          id={selectId}
          className={`${inputClass} w-auto min-w-40 flex-1`}
          value={selected}
          disabled={saving}
          onChange={(event) => {
            setSelected(event.target.value as QuoteStatus);
            setFeedback(null);
          }}
        >
          {QUOTE_STATUSES.map((status) => (
            <option key={status} value={status}>
              {STATUS_LABELS[status]}
              {status === quote.status ? " (current)" : ""}
            </option>
          ))}
        </select>
        <button type="button" className={buttonPrimary} disabled={unchanged || saving} onClick={openConfirm}>
          {saving ? "Saving…" : "Change status"}
        </button>
      </div>

      {/* role="status": anuncia el resultado sin mover el foco; vacío no dice nada */}
      <p role="status" className={`mt-2 text-sm ${feedback ? FEEDBACK_CLASSES[feedback.kind] : ""}`}>
        {feedback?.text}
      </p>

      <dialog
        ref={dialogRef}
        aria-labelledby={`${selectId}-title`}
        className="m-auto w-[calc(100%-2rem)] max-w-md rounded-xl border border-ink-200 bg-white p-6 shadow-xl backdrop:bg-ink-900/50"
      >
        <h2 id={`${selectId}-title`} className="font-display text-lg font-semibold text-ink-900">
          Change status?
        </h2>
        <p className="mt-2 text-ink-700">
          <strong>{quote.name}</strong> will move from <strong>{STATUS_LABELS[quote.status]}</strong> to{" "}
          <strong>{STATUS_LABELS[selected]}</strong>. The change is recorded in the status history.
        </p>
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          {/* autoFocus en Cancel: Enter por accidente no confirma */}
          <button type="button" className={buttonSecondary} autoFocus onClick={() => dialogRef.current?.close()}>
            Cancel
          </button>
          <button type="button" className={buttonPrimary} onClick={confirm}>
            Change to {STATUS_LABELS[selected]}
          </button>
        </div>
      </dialog>
    </div>
  );
}
