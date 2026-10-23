import { usePageTitle } from "../lib/hooks";

// Provisional: la lista llega en el siguiente commit
export function QuotesListPage() {
  usePageTitle("Quotes");
  return <h1 className="font-display text-2xl font-bold text-ink-900">Quotes</h1>;
}
