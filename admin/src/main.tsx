import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./index.css";

const root = document.getElementById("root");
if (!root) throw new Error("Falta el elemento #root en index.html");

// StrictMode: en desarrollo ejecuta dos veces los efectos para detectar los que no se limpian bien
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
