import { useEffect, useRef } from "react";

/** Título de la pestaña del navegador (lo anuncian los lectores de pantalla al cambiar de página). */
export function usePageTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} · Fernwick Admin`;
  }, [title]);
}

/**
 * Lleva el foco al título de la página cuando aparece. En una SPA el navegador no recarga la
 * página al navegar, así que sin esto un lector de pantalla no se entera de que cambió.
 * El elemento necesita tabIndex={-1} para poder recibir foco por código.
 */
export function useFocusOnMount<T extends HTMLElement>(enabled = true) {
  const ref = useRef<T>(null);
  useEffect(() => {
    if (enabled) ref.current?.focus();
  }, [enabled]);
  return ref;
}
