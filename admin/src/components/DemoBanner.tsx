/*
  Aviso permanente del modo demo. Es solo informativo: la protección real está en la API
  (403 al escribir) y en la base (RLS: el rol fernwick_demo solo ve filas is_demo).
*/
export function DemoBanner() {
  return (
    <div role="note" className="border-b border-sun-200 bg-sun-50 px-4 py-2 text-center text-sm text-sun-800">
      <strong className="font-semibold">Demo mode — fictional data.</strong>{" "}
      <span>Read-only: all names, emails and phone numbers are made up.</span>
    </div>
  );
}
