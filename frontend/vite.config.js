import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite is the tool that runs the React app during development (http://localhost:5173).
//
// The "proxy" setting forwards every request starting with /api to the FastAPI
// backend on port 8000. To the browser, frontend and backend then look like ONE
// website, which means:
//   - login cookies work without extra setup
//   - we don't need CORS rules (the browser's cross-website security checks)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
