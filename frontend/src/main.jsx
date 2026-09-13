// Entry point of the React app: finds <div id="root"> in index.html and draws <App /> inside it.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  // StrictMode runs extra checks during development to warn about common mistakes.
  <StrictMode>
    <App />
  </StrictMode>
);
