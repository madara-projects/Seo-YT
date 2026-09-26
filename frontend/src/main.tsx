import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./styles/index.css";

const container = document.getElementById("root");
if (!container) throw new Error("Root container #root was not found.");

createRoot(container).render(
  <StrictMode>
    {/* FastAPI serves the SPA under /next while the classic dashboard keeps /app. */}
    <BrowserRouter basename="/next">
      <App />
    </BrowserRouter>
  </StrictMode>,
);
