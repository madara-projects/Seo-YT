import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./styles/index.css";

const container = document.getElementById("root");
if (!container) throw new Error("Root container #root was not found.");

createRoot(container).render(
  <StrictMode>
    {/* FastAPI serves the app at the root and on each page path (routes.py). */}
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
