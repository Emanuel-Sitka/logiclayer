import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "@xyflow/react/dist/style.css";
import "./styles.css";

function readData() {
  const tag = document.getElementById("logiclayer-data");
  if (!tag) return null;
  try {
    return JSON.parse(tag.textContent);
  } catch {
    return null;
  }
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App data={readData()} />
  </React.StrictMode>,
);
