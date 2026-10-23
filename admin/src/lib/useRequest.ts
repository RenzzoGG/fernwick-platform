import { useCallback, useEffect, useState } from "react";
import { isAbortError } from "../api/client";

interface RequestState<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
}

/**
 * Carga datos de la API con estado de carga, error y "reintentar".
 *
 * - `key` resume todo lo que cambia la petición (p. ej. la query string). Cuando cambia, se
 *   vuelve a pedir; `load` no va en las dependencias del efecto a propósito: es una función
 *   nueva en cada render y provocaría peticiones infinitas.
 * - AbortController cancela la petición anterior: si el usuario cambia el filtro dos veces
 *   rápido, una respuesta lenta y vieja no puede pisar a la nueva.
 * - keepPrevious: mientras carga lo nuevo, se siguen mostrando los datos anteriores
 *   (la lista no "parpadea" al cambiar de página).
 */
export function useRequest<T>(load: (signal: AbortSignal) => Promise<T>, key: string, keepPrevious = false) {
  const [state, setState] = useState<RequestState<T>>({ data: undefined, error: null, loading: true });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState((prev) => ({ data: keepPrevious ? prev.data : undefined, error: null, loading: true }));
    load(controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error: unknown) => {
        if (isAbortError(error)) return;
        setState((prev) => ({ data: keepPrevious ? prev.data : undefined, error, loading: false }));
      });
    return () => controller.abort();
  }, [key, attempt, keepPrevious]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, retry };
}
