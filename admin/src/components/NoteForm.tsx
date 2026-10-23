import { useId, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { addQuoteNote } from "../api/quotes";
import { NOTE_BODY_MAX, type Note } from "../api/types";
import { buttonPrimary, inputClass, labelClass } from "../lib/ui";

/*
  Largo en "code points" ([...texto].length), como char_length de PostgreSQL y len() de Python.
  `.length` de JS cuenta unidades UTF-16: un emoji vale 2 y el panel rechazaría notas válidas.
*/
function charCount(text: string): number {
  return [...text].length;
}

// El contador se anuncia al lector de pantalla solo cerca del límite (no en cada tecla)
const WARN_AT = NOTE_BODY_MAX - 100;

interface Props {
  quoteId: number;
  onAdded: (note: Note) => void;
}

/** Formulario de nota interna (solo admin; la página no lo muestra al demo). */
export function NoteForm({ quoteId, onAdded }: Props) {
  const id = useId();
  const savingRef = useRef(false); // cerrojo contra el doble clic (ver StatusControl)
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Se mide recortado: la API recorta los espacios antes de validar (str_strip_whitespace)
  const length = charCount(body.trim());
  const tooLong = length > NOTE_BODY_MAX;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault(); // sin esto, el navegador recargaría la página al enviar
    if (savingRef.current) return;
    setSuccess(false);
    if (length === 0) return setError("Write a note first.");
    if (tooLong) return setError(`Notes can be at most ${NOTE_BODY_MAX} characters.`);

    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      const note = await addQuoteNote(quoteId, body.trim());
      onAdded(note);
      setBody("");
      setSuccess(true);
    } catch (err) {
      // Se conserva el texto: el usuario no pierde lo que escribió
      if (!(err instanceof ApiError)) setError("Something went wrong. Please try again.");
      else if (err.status === 401) return; // sesión vencida: AuthContext manda al login
      else if (err.status === 403) setError("Your account can't add notes (read-only).");
      else if (err.status === 404) setError("This quote no longer exists.");
      else setError(`${err.message}${err.status === 422 ? "" : " Please try again."}`);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="mt-4 border-t border-ink-200 pt-4">
      <label htmlFor={id} className={labelClass}>
        Add a note
      </label>
      <textarea
        id={id}
        rows={3}
        className={`${inputClass} resize-y`}
        value={body}
        readOnly={saving}
        aria-invalid={error !== null || tooLong}
        aria-describedby={`${id}-count ${id}-error`}
        onChange={(event) => {
          setBody(event.target.value);
          setError(null);
          setSuccess(false);
        }}
      />
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 text-sm">
          <p id={`${id}-error`} role="alert" className="text-danger-600">
            {error}
          </p>
          <p role="status" className="text-brand-800">
            {success ? "Note added." : ""}
          </p>
        </div>
        <p
          id={`${id}-count`}
          aria-live={length >= WARN_AT ? "polite" : "off"}
          className={`text-sm tabular-nums ${tooLong ? "font-semibold text-danger-600" : "text-ink-500"}`}
        >
          {length} / {NOTE_BODY_MAX}
        </p>
      </div>
      <button type="submit" className={`${buttonPrimary} mt-2`} disabled={saving}>
        {saving ? "Saving…" : "Add note"}
      </button>
    </form>
  );
}
