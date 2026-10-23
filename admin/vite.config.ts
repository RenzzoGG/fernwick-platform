import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// Vite sirve el panel en desarrollo (puerto 5173, permitido en CORS_ORIGINS de la API)
// y en el build genera dist/, que Railway sirve como sitio estático.
export default defineConfig(({ command, mode }) => {
  // Sin VITE_API_URL el panel apuntaría a localhost: mejor que el build falle en Railway
  // a publicar un panel roto. En desarrollo (`npm run dev`) se usa la API local.
  const env = loadEnv(mode, ".", "VITE_");
  if (command === "build" && !env.VITE_API_URL) {
    throw new Error("Falta VITE_API_URL (copia .env.example como .env, o defínela en Railway)");
  }

  return {
    plugins: [react(), tailwindcss()],
    server: { port: 5173, strictPort: true },
    preview: { port: 4173, strictPort: true },
  };
});
