import type { ReactNode } from "react";
import { buttonSecondary, cardClass } from "../lib/ui";

/*
  Estados de una vista mientras llegan los datos. role="status" y role="alert" hacen que un
  lector de pantalla anuncie el cambio sin que el usuario tenga que buscarlo.
*/

export function LoadingState({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-3 py-16 text-ink-600">
      <span className="size-5 animate-spin rounded-full border-2 border-ink-300 border-t-brand-700" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  children,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  children?: ReactNode;
}) {
  return (
    <div role="alert" className={`${cardClass} border-danger-600/30 bg-danger-50 px-5 py-6`}>
      <h2 className="font-display text-lg font-semibold text-danger-600">{title}</h2>
      <p className="mt-1 text-ink-700">{message}</p>
      {(onRetry || children) && (
        <div className="mt-4 flex flex-wrap gap-3">
          {onRetry && (
            <button type="button" className={buttonSecondary} onClick={onRetry}>
              Try again
            </button>
          )}
          {children}
        </div>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div role="status" className={`${cardClass} px-5 py-12 text-center`}>
      <h2 className="font-display text-lg font-semibold text-ink-900">{title}</h2>
      {children && <div className="mt-2 text-ink-600">{children}</div>}
    </div>
  );
}
