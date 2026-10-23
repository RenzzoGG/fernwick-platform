import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Vite sirve el panel en desarrollo (puerto 5173, permitido en CORS_ORIGINS de la API)
// y en el build genera dist/, que Railway sirve como sitio estático.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
});
