/// <reference types="vite/client" />

// Variables de entorno que el panel lee con import.meta.env (Vite solo expone las VITE_*)
interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
