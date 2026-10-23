/*
  Clases de Tailwind compartidas por botones y campos. Van como textos completos (nunca armados
  concatenando pedazos): el escáner de Tailwind solo genera las clases que encuentra escritas.
  min-h-11 = 44 px: tamaño mínimo cómodo para tocar en el celular.
*/
export const buttonPrimary =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-brand-700 px-4 py-2 font-semibold text-white hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-60";

export const buttonSecondary =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-ink-300 bg-white px-4 py-2 font-semibold text-ink-900 hover:bg-ink-100 disabled:cursor-not-allowed disabled:opacity-60";

export const inputClass =
  "block min-h-11 w-full rounded-lg border border-ink-300 bg-white px-3 py-2 text-ink-900 placeholder:text-ink-500 focus-visible:border-brand-700";

export const labelClass = "mb-1 block text-sm font-semibold text-ink-900";

export const linkClass = "font-semibold text-brand-700 underline-offset-2 hover:underline";

export const cardClass = "rounded-xl border border-ink-200 bg-white shadow-sm";
