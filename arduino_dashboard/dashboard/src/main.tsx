import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import { App } from "./App";

const host = document.getElementById("root");
if (!host) throw new Error("#root element is missing");

createRoot(host).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
