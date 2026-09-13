import { useEffect, useState } from "react";

import { apiGet } from "../api.js";

/**
 * BackendStatus — asks the FastAPI backend "are you alive?" and shows the answer.
 *
 * It proves the whole chain works: browser -> Vite dev server -> proxy -> FastAPI.
 */
export default function BackendStatus() {
  // "State" = values that, when changed, make React redraw this component.
  const [health, setHealth] = useState(null); // JSON from /api/health once it arrives
  const [error, setError] = useState(null); // error message if the backend can't be reached

  // useEffect with an empty [] list runs once, right after the component first appears.
  useEffect(() => {
    apiGet("/api/health")
      .then((data) => setHealth(data))
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <p className="status status-bad">
        ✗ Backend not reachable: {error}. Is <code>uvicorn pantrypilot.web.main:app --reload</code> running?
      </p>
    );
  }

  if (!health) {
    return <p className="status">Checking backend…</p>;
  }

  return (
    <p className="status status-good">
      ✓ Backend connected — {health.app} server time {new Date(health.server_time).toLocaleTimeString()}
    </p>
  );
}
