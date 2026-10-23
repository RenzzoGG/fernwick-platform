import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";

const root = document.getElementById("root");
if (!root) throw new Error("Falta el elemento #root en index.html");

createRoot(root).render(
  <StrictMode>
    <main className="p-8">
      <h1 className="font-display text-2xl font-bold text-ink-900">Fernwick Admin</h1>
    </main>
  </StrictMode>,
);
